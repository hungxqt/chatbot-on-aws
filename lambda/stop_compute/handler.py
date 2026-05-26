"""
Stop billable RDS, ECS, and EC2 compute that is not explicitly protected.

Protection rule:
- Any resource tagged Environment=Production is skipped.
- Any resource tagged Environment=Development and Keep=True is skipped.
- All other RDS, ECS, and EC2 targets are eligible unless narrowed by TARGET_ENVIRONMENT.

EC2 handling:
- Instances: StopInstances when running.

RDS handling:
- DB instances: StopDBInstance when available and currently running.
- DB clusters: StopDBCluster when available and currently available.

ECS handling:
- Services: UpdateService desiredCount=0 when currently above zero.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError


AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
KEEP_TAG_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
TARGET_ENVIRONMENT = os.environ.get("TARGET_ENVIRONMENT", "").strip()
KEEP_TAG_KEY = os.environ.get("KEEP_TAG_KEY", "Keep").strip().lower()
ENVIRONMENT_TAG_KEY = os.environ.get("ENVIRONMENT_TAG_KEY", "Environment").strip().lower()
PRODUCTION_ENVIRONMENT_VALUE = os.environ.get("PRODUCTION_ENVIRONMENT_VALUE", "Production").strip().lower()
DEVELOPMENT_ENVIRONMENT_VALUE = os.environ.get("DEVELOPMENT_ENVIRONMENT_VALUE", "Development").strip().lower()

rds = boto3.client("rds", region_name=AWS_REGION)
ecs = boto3.client("ecs", region_name=AWS_REGION)
ec2 = boto3.client("ec2", region_name=AWS_REGION)


def _bool_from_event(event: dict[str, Any], key: str, default: bool) -> bool:
    value = event.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in KEEP_TAG_TRUE_VALUES
    return bool(value)


def _tag_map(tags: list[dict[str, str]]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for tag in tags:
        key = tag.get("Key") or tag.get("key")
        value = tag.get("Value") or tag.get("value") or ""
        if key:
            mapped[str(key).strip().lower()] = str(value).strip()
    return mapped


def _is_keep_protected(tags: dict[str, str]) -> bool:
    return tags.get(KEEP_TAG_KEY, "").strip().lower() in KEEP_TAG_TRUE_VALUES


def _environment_value(tags: dict[str, str]) -> str:
    return tags.get(ENVIRONMENT_TAG_KEY, "").strip().lower()


def _matches_environment(tags: dict[str, str], target_environment: str) -> bool:
    if not target_environment:
        return True
    return _environment_value(tags) == target_environment.lower()


def _eligible(tags: dict[str, str], target_environment: str) -> tuple[bool, str]:
    environment = _environment_value(tags)
    if environment == PRODUCTION_ENVIRONMENT_VALUE:
        return False, f"{ENVIRONMENT_TAG_KEY}=Production"
    if environment == DEVELOPMENT_ENVIRONMENT_VALUE and _is_keep_protected(tags):
        return False, f"{ENVIRONMENT_TAG_KEY}=Development and {KEEP_TAG_KEY}=True"
    if not _matches_environment(tags, target_environment):
        return False, f"Environment tag does not match {target_environment}"
    return True, "eligible"


def _rds_tags(arn: str) -> dict[str, str]:
    return _tag_map(rds.list_tags_for_resource(ResourceName=arn).get("TagList", []))


def _ecs_tags(arn: str) -> dict[str, str]:
    return _tag_map(ecs.list_tags_for_resource(resourceArn=arn).get("tags", []))


def _ec2_tags(instance: dict[str, Any]) -> dict[str, str]:
    return _tag_map(instance.get("Tags", []))


def _record(
    results: list[dict[str, Any]],
    service: str,
    resource_type: str,
    resource_id: str,
    action: str,
    status: str,
    reason: str = "",
) -> None:
    results.append(
        {
            "service": service,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "status": status,
            "reason": reason,
        }
    )


def stop_rds_instances(results: list[dict[str, Any]], dry_run: bool, target_environment: str) -> None:
    paginator = rds.get_paginator("describe_db_instances")
    for page in paginator.paginate():
        for instance in page.get("DBInstances", []):
            instance_id = instance["DBInstanceIdentifier"]
            instance_arn = instance["DBInstanceArn"]
            state = instance.get("DBInstanceStatus", "unknown")
            engine = instance.get("Engine", "")
            tags = _rds_tags(instance_arn)
            eligible, reason = _eligible(tags, target_environment)

            if not eligible:
                _record(results, "rds", "db-instance", instance_id, "stop", "skipped", reason)
                continue
            if state != "available":
                _record(results, "rds", "db-instance", instance_id, "stop", "skipped", f"state={state}")
                continue
            if instance.get("ReadReplicaSourceDBInstanceIdentifier"):
                _record(results, "rds", "db-instance", instance_id, "stop", "skipped", "read replica")
                continue
            if engine.startswith("aurora"):
                _record(results, "rds", "db-instance", instance_id, "stop", "skipped", "aurora instance stopped via cluster")
                continue

            if dry_run:
                _record(results, "rds", "db-instance", instance_id, "stop", "dry_run", reason)
                continue

            try:
                rds.stop_db_instance(DBInstanceIdentifier=instance_id)
                _record(results, "rds", "db-instance", instance_id, "stop", "started", reason)
            except ClientError as exc:
                _record(results, "rds", "db-instance", instance_id, "stop", "error", str(exc))


def stop_rds_clusters(results: list[dict[str, Any]], dry_run: bool, target_environment: str) -> None:
    paginator = rds.get_paginator("describe_db_clusters")
    for page in paginator.paginate():
        for cluster in page.get("DBClusters", []):
            cluster_id = cluster["DBClusterIdentifier"]
            cluster_arn = cluster["DBClusterArn"]
            state = cluster.get("Status", "unknown")
            engine = cluster.get("Engine", "")
            tags = _rds_tags(cluster_arn)
            eligible, reason = _eligible(tags, target_environment)

            if not eligible:
                _record(results, "rds", "db-cluster", cluster_id, "stop", "skipped", reason)
                continue
            if state != "available":
                _record(results, "rds", "db-cluster", cluster_id, "stop", "skipped", f"state={state}")
                continue
            if engine == "docdb":
                _record(results, "rds", "db-cluster", cluster_id, "stop", "skipped", "docdb is not targeted")
                continue

            if dry_run:
                _record(results, "rds", "db-cluster", cluster_id, "stop", "dry_run", reason)
                continue

            try:
                rds.stop_db_cluster(DBClusterIdentifier=cluster_id)
                _record(results, "rds", "db-cluster", cluster_id, "stop", "started", reason)
            except ClientError as exc:
                _record(results, "rds", "db-cluster", cluster_id, "stop", "error", str(exc))


def stop_ecs_services(results: list[dict[str, Any]], dry_run: bool, target_environment: str) -> None:
    cluster_paginator = ecs.get_paginator("list_clusters")
    for cluster_page in cluster_paginator.paginate():
        for cluster_arn in cluster_page.get("clusterArns", []):
            service_paginator = ecs.get_paginator("list_services")
            for service_page in service_paginator.paginate(cluster=cluster_arn):
                service_arns = service_page.get("serviceArns", [])
                if not service_arns:
                    continue

                for service in _describe_ecs_services(cluster_arn, service_arns):
                    service_arn = service["serviceArn"]
                    service_name = service["serviceName"]
                    desired_count = int(service.get("desiredCount", 0))
                    status = service.get("status", "UNKNOWN")
                    tags = _ecs_tags(service_arn)
                    eligible, reason = _eligible(tags, target_environment)

                    if not eligible:
                        _record(results, "ecs", "service", service_arn, "set_desired_count_0", "skipped", reason)
                        continue
                    if status != "ACTIVE":
                        _record(results, "ecs", "service", service_arn, "set_desired_count_0", "skipped", f"status={status}")
                        continue
                    if desired_count == 0:
                        _record(results, "ecs", "service", service_arn, "set_desired_count_0", "skipped", "desiredCount already 0")
                        continue

                    if dry_run:
                        _record(results, "ecs", "service", service_arn, "set_desired_count_0", "dry_run", reason)
                        continue

                    try:
                        ecs.update_service(cluster=cluster_arn, service=service_name, desiredCount=0)
                        _record(results, "ecs", "service", service_arn, "set_desired_count_0", "started", reason)
                    except ClientError as exc:
                        _record(results, "ecs", "service", service_arn, "set_desired_count_0", "error", str(exc))


def _describe_ecs_services(cluster_arn: str, service_arns: list[str]) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    for index in range(0, len(service_arns), 10):
        batch = service_arns[index:index + 10]
        response = ecs.describe_services(cluster=cluster_arn, services=batch)
        services.extend(response.get("services", []))
    return services


def stop_ec2_instances(results: list[dict[str, Any]], dry_run: bool, target_environment: str) -> None:
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_id = instance["InstanceId"]
                state = instance.get("State", {}).get("Name", "unknown")
                tags = _ec2_tags(instance)
                eligible, reason = _eligible(tags, target_environment)

                if not eligible:
                    _record(results, "ec2", "instance", instance_id, "stop", "skipped", reason)
                    continue
                if state != "running":
                    _record(results, "ec2", "instance", instance_id, "stop", "skipped", f"state={state}")
                    continue

                if dry_run:
                    _record(results, "ec2", "instance", instance_id, "stop", "dry_run", reason)
                    continue

                try:
                    ec2.stop_instances(InstanceIds=[instance_id])
                    _record(results, "ec2", "instance", instance_id, "stop", "started", reason)
                except ClientError as exc:
                    _record(results, "ec2", "instance", instance_id, "stop", "error", str(exc))


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    event = event or {}
    if isinstance(event.get("body"), str):
        try:
            event.update(json.loads(event["body"]))
        except json.JSONDecodeError:
            pass

    dry_run = _bool_from_event(event, "dry_run", os.environ.get("DRY_RUN", "false").lower() == "true")
    target_environment = str(event.get("target_environment", TARGET_ENVIRONMENT)).strip()

    results: list[dict[str, Any]] = []
    stop_rds_instances(results, dry_run, target_environment)
    stop_rds_clusters(results, dry_run, target_environment)
    stop_ecs_services(results, dry_run, target_environment)
    stop_ec2_instances(results, dry_run, target_environment)

    summary = {
        "started": sum(1 for result in results if result["status"] == "started"),
        "dry_run": sum(1 for result in results if result["status"] == "dry_run"),
        "skipped": sum(1 for result in results if result["status"] == "skipped"),
        "errors": sum(1 for result in results if result["status"] == "error"),
    }

    return {
        "statusCode": 200 if summary["errors"] == 0 else 207,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
                "target_environment": target_environment or None,
                "summary": summary,
                "results": results,
            },
            default=str,
        ),
    }
