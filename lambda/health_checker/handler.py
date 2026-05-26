"""
AWS Lambda health checker for ai_agent infrastructure.

Checks: PostgreSQL (Aurora), Redis (ElastiCache), AWS Bedrock,
Bedrock Knowledge Base, EFS mount, and the main FastAPI app.

All checks run in parallel with per-check timeouts so one
unreachable service cannot block the entire response.

Deploy in the same VPC private subnets as the backend ECS service
so it can reach RDS, Redis, and EFS directly.
"""

import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone

import boto3
import psycopg2
import redis as redis_lib
from botocore.config import Config

CHECK_TIMEOUT = int(os.environ.get("CHECK_TIMEOUT_SECONDS", "8"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_boto_cfg = Config(connect_timeout=5, read_timeout=5, retries={"max_attempts": 1})
_bedrock_client = boto3.client("bedrock", region_name=AWS_REGION, config=_boto_cfg)
_bedrock_agent_client = boto3.client("bedrock-agent", region_name=AWS_REGION, config=_boto_cfg)
_ecs_client = boto3.client("ecs", region_name=AWS_REGION, config=_boto_cfg)


def check_database() -> dict:
    """Check PostgreSQL (Aurora) connectivity."""
    host = os.environ.get("POSTGRES_HOST")
    if not host:
        return {"status": "skipped", "reason": "POSTGRES_HOST not configured"}

    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dbname = os.environ.get("POSTGRES_DB", "ai_agent")

    start = time.monotonic()
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password,
            dbname=dbname, connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms, "type": "aurora-postgresql"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "type": "aurora-postgresql"}


def check_redis() -> dict:
    """Check Redis (ElastiCache) connectivity."""
    host = os.environ.get("REDIS_HOST")
    if not host:
        return {"status": "skipped", "reason": "REDIS_HOST not configured"}

    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD")
    use_ssl = os.environ.get("REDIS_SSL", "true").lower() == "true"

    start = time.monotonic()
    try:
        r = redis_lib.Redis(
            host=host, port=port, password=password,
            ssl=use_ssl, socket_connect_timeout=5, socket_timeout=5,
        )
        r.ping()
        r.close()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_bedrock() -> dict:
    """Check AWS Bedrock availability by listing foundation models."""
    start = time.monotonic()
    try:
        resp = _bedrock_client.list_foundation_models(byOutputModality="TEXT")
        model_count = len(resp.get("modelSummaries", []))
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "region": AWS_REGION,
            "available_models": model_count,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "region": AWS_REGION}


def check_bedrock_kb() -> dict:
    """Check Bedrock Knowledge Base availability."""
    kb_id = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID")
    if not kb_id:
        return {"status": "skipped", "reason": "BEDROCK_KNOWLEDGE_BASE_ID not configured"}

    start = time.monotonic()
    try:
        resp = _bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
        kb = resp.get("knowledgeBase", {})
        kb_status = kb.get("status", "UNKNOWN")
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        healthy = kb_status == "ACTIVE"
        return {
            "status": "healthy" if healthy else "unhealthy",
            "latency_ms": latency_ms,
            "knowledge_base_id": kb_id,
            "kb_status": kb_status,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "knowledge_base_id": kb_id}


def check_efs() -> dict:
    """Check EFS mount accessibility."""
    efs_mount = os.environ.get("EFS_MOUNT_DIR", "/mnt/efs")

    start = time.monotonic()
    try:
        test_path = os.path.join(efs_mount, ".health_check")
        with open(test_path, "w") as f:
            f.write("ok")
        with open(test_path) as f:
            content = f.read()
        os.remove(test_path)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        if content == "ok":
            return {"status": "healthy", "latency_ms": latency_ms, "mount": efs_mount}
        return {"status": "unhealthy", "error": "Read/write mismatch", "mount": efs_mount}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "mount": efs_mount}


def check_main_app() -> dict:
    """Check the main FastAPI backend via its health endpoint."""
    app_url = os.environ.get("MAIN_APP_HEALTH_URL")
    if not app_url:
        return {"status": "skipped", "reason": "MAIN_APP_HEALTH_URL not configured"}

    api_key = os.environ.get("MAIN_APP_API_KEY", "")

    start = time.monotonic()
    try:
        req = urllib.request.Request(app_url, method="GET")
        if api_key:
            req.add_header("x-api-key", api_key)
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        app_status = body.get("status", "unknown")
        return {
            "status": "healthy" if app_status == "healthy" else "degraded",
            "latency_ms": latency_ms,
            "app_status": app_status,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_ecs_services() -> dict:
    """Check ECS service statuses (backend, worker, scheduler)."""
    cluster = os.environ.get("ECS_CLUSTER_NAME")
    if not cluster:
        return {"status": "skipped", "reason": "ECS_CLUSTER_NAME not configured"}

    try:
        services_resp = _ecs_client.list_services(cluster=cluster)
        service_arns = services_resp.get("serviceArns", [])

        if not service_arns:
            return {"status": "unhealthy", "error": "No services found in cluster"}

        desc = _ecs_client.describe_services(cluster=cluster, services=service_arns)
        services = {}
        all_stable = True

        for svc in desc.get("services", []):
            name = svc["serviceName"]
            running = svc.get("runningCount", 0)
            desired = svc.get("desiredCount", 0)
            svc_status = svc.get("status", "UNKNOWN")
            stable = running >= desired and svc_status == "ACTIVE"
            if not stable:
                all_stable = False
            services[name] = {
                "status": "healthy" if stable else "unhealthy",
                "running": running,
                "desired": desired,
                "ecs_status": svc_status,
            }

        return {
            "status": "healthy" if all_stable else "degraded",
            "services": services,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


CRITICAL_CHECKS = {"database", "redis"}

CHECKS = {
    "database": check_database,
    "redis": check_redis,
    "bedrock": check_bedrock,
    "bedrock_kb": check_bedrock_kb,
    "efs": check_efs,
    "main_app": check_main_app,
    "ecs_services": check_ecs_services,
}


def _run_check(name: str, check_fn) -> tuple[str, dict]:
    """Run a single check with crash protection."""
    try:
        return name, check_fn()
    except Exception as e:
        return name, {"status": "unhealthy", "error": f"Check crashed: {e}"}


def lambda_handler(event, context):
    """Main Lambda handler - returns JSON health data."""
    checks = {}

    with ThreadPoolExecutor(max_workers=len(CHECKS)) as executor:
        futures = {
            name: executor.submit(_run_check, name, fn)
            for name, fn in CHECKS.items()
        }
        for name, future in futures.items():
            try:
                _, result = future.result(timeout=CHECK_TIMEOUT)
                checks[name] = result
            except TimeoutError:
                checks[name] = {
                    "status": "unhealthy",
                    "error": f"Timed out after {CHECK_TIMEOUT}s",
                }
            except Exception as e:
                checks[name] = {"status": "unhealthy", "error": f"Check crashed: {e}"}

    unhealthy_critical = any(
        checks.get(name, {}).get("status") != "healthy"
        for name in CRITICAL_CHECKS
        if checks.get(name, {}).get("status") != "skipped"
    )
    any_unhealthy = any(
        c.get("status") == "unhealthy"
        for c in checks.values()
    )

    if unhealthy_critical:
        overall = "unhealthy"
    elif any_unhealthy:
        overall = "degraded"
    else:
        overall = "healthy"

    body = {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "ai_agent",
        "checks": checks,
    }

    status_code = 200 if overall == "healthy" else 503 if overall == "unhealthy" else 207

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store",
        },
        "body": json.dumps(body, default=str),
    }
