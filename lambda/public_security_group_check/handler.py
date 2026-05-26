"""
Check security groups for public inbound access to sensitive ports.

Default policy:
- Find ingress rules that expose TCP 22 or 5432 to 0.0.0.0/0.
- Revoke only the 0.0.0.0/0 ingress entry from matching rules.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError


AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
DEFAULT_PORTS = (22, 5432)
PUBLIC_IPV4_CIDR = "0.0.0.0/0"

ec2 = boto3.client("ec2", region_name=AWS_REGION)


def _ports_from_event(event: dict[str, Any] | None) -> list[int]:
    if event and "ports" in event:
        raw_ports = event["ports"]
    else:
        raw_ports = os.environ.get("PORTS", ",".join(str(port) for port in DEFAULT_PORTS))

    if isinstance(raw_ports, str):
        parts = [part.strip() for part in raw_ports.split(",") if part.strip()]
    elif isinstance(raw_ports, list):
        parts = raw_ports
    else:
        parts = DEFAULT_PORTS

    ports: list[int] = []
    for part in parts:
        try:
            port = int(part)
        except (TypeError, ValueError):
            continue
        if 0 <= port <= 65535 and port not in ports:
            ports.append(port)

    return ports or list(DEFAULT_PORTS)


def _is_truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _dry_run_from_event(event: dict[str, Any] | None) -> bool:
    if event and "dry_run" in event:
        return _is_truthy(event["dry_run"])
    return _is_truthy(os.environ.get("DRY_RUN", "false"))


def _rule_exposes_port(permission: dict[str, Any], port: int) -> bool:
    protocol = str(permission.get("IpProtocol", "")).lower()
    if protocol == "-1":
        return True
    if protocol not in {"tcp", "6"}:
        return False

    from_port = permission.get("FromPort")
    to_port = permission.get("ToPort")
    if from_port is None or to_port is None:
        return False

    return int(from_port) <= port <= int(to_port)


def _public_ipv4_ranges(permission: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"CidrIp": PUBLIC_IPV4_CIDR}
        for ip_range in permission.get("IpRanges", [])
        if ip_range.get("CidrIp") == PUBLIC_IPV4_CIDR
    ]


def _matching_public_ports(permission: dict[str, Any], ports: list[int]) -> list[int]:
    if not _public_ipv4_ranges(permission):
        return []
    return [port for port in ports if _rule_exposes_port(permission, port)]


def _describe_security_groups() -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    paginator = ec2.get_paginator("describe_security_groups")
    for page in paginator.paginate():
        groups.extend(page.get("SecurityGroups", []))
    return groups


def _group_findings(group: dict[str, Any], ports: list[int]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for permission in group.get("IpPermissions", []):
        exposed_ports = _matching_public_ports(permission, ports)
        if not exposed_ports:
            continue

        findings.append(
            {
                "group_id": group.get("GroupId"),
                "group_name": group.get("GroupName"),
                "vpc_id": group.get("VpcId"),
                "exposed_ports": exposed_ports,
                "cidr": PUBLIC_IPV4_CIDR,
                "protocol": permission.get("IpProtocol"),
                "from_port": permission.get("FromPort"),
                "to_port": permission.get("ToPort"),
                "revocation_permission": _revocation_permission(permission),
                "rule_description": [
                    ip_range.get("Description", "")
                    for ip_range in permission.get("IpRanges", [])
                    if ip_range.get("CidrIp") == PUBLIC_IPV4_CIDR
                ],
            }
        )

    return findings


def _revocation_permission(permission: dict[str, Any]) -> dict[str, Any]:
    revoke_permission: dict[str, Any] = {
        "IpProtocol": permission.get("IpProtocol"),
        "IpRanges": _public_ipv4_ranges(permission),
    }

    if permission.get("IpProtocol") != "-1":
        revoke_permission["FromPort"] = permission.get("FromPort")
        revoke_permission["ToPort"] = permission.get("ToPort")

    return revoke_permission


def _revoke_public_ingress(finding: dict[str, Any]) -> dict[str, Any]:
    response = ec2.revoke_security_group_ingress(
        GroupId=finding["group_id"],
        IpPermissions=[finding["revocation_permission"]],
    )
    return {
        "return": response.get("Return"),
        "revoked_security_group_rules": response.get("RevokedSecurityGroupRules", []),
        "unknown_ip_permissions": response.get("UnknownIpPermissions", []),
    }


def lambda_handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    ports = _ports_from_event(event)
    dry_run = _dry_run_from_event(event)

    try:
        groups = _describe_security_groups()
        findings: list[dict[str, Any]] = []
        for group in groups:
            findings.extend(_group_findings(group, ports))

        revoke_failures = 0
        for finding in findings:
            if dry_run:
                finding["action"] = "would_revoke"
                finding["revoked"] = False
                continue

            try:
                finding["revoke_response"] = _revoke_public_ingress(finding)
                finding["action"] = "revoked"
                finding["revoked"] = True
            except ClientError as exc:
                revoke_failures += 1
                finding["action"] = "revoke_failed"
                finding["revoked"] = False
                finding["revoke_error"] = str(exc)

        if not findings:
            status = "passed"
            status_code = 200
        elif dry_run:
            status = "would_revoke"
            status_code = 207
        elif revoke_failures:
            status = "partial_failure"
            status_code = 207
        else:
            status = "remediated"
            status_code = 200

        body = {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "region": AWS_REGION,
            "dry_run": dry_run,
            "checked_cidr": PUBLIC_IPV4_CIDR,
            "checked_ports": ports,
            "security_groups_scanned": len(groups),
            "finding_count": len(findings),
            "revoked_count": sum(1 for finding in findings if finding.get("revoked")),
            "revoke_failure_count": revoke_failures,
            "findings": findings,
        }
    except ClientError as exc:
        status_code = 500
        body = {
            "status": "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "region": AWS_REGION,
            "error": str(exc),
        }

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store",
        },
        "body": json.dumps(body, default=str),
    }
