"""
Zero-dependency AWS Lambda health checker for ai_agent infrastructure.

Uses only Python stdlib — no boto3, psycopg2, or redis packages.
- PostgreSQL / Redis: raw TCP socket + protocol bytes
- AWS APIs (Bedrock, ECS): SigV4-signed HTTP requests via urllib
- EFS: filesystem read/write
- Main app: plain HTTP GET

Deployment zip is ~50KB (just this file + dashboard_html.py).
"""

import hashlib
import hmac
import json
import os
import socket
import struct
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone

from dashboard_html import DASHBOARD_HTML

CHECK_TIMEOUT = int(os.environ.get("CHECK_TIMEOUT_SECONDS", "8"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SOCKET_TIMEOUT = 5


# ---------------------------------------------------------------------------
# AWS SigV4 signing (stdlib only)
# ---------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_aws_credentials() -> tuple[str, str, str]:
    return (
        os.environ.get("AWS_ACCESS_KEY_ID", ""),
        os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        os.environ.get("AWS_SESSION_TOKEN", ""),
    )


def _sigv4_request(method: str, url: str, service: str, body: bytes = b"",
                   extra_headers: dict | None = None) -> dict:
    """Make a SigV4-signed request using only urllib."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname
    path = parsed.path or "/"
    query = parsed.query

    access_key, secret_key, session_token = _get_aws_credentials()
    now = datetime.now(timezone.utc)
    datestamp = now.strftime("%Y%m%d")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")

    canonical_querystring = query
    payload_hash = _sha256(body)

    headers = {
        "Host": host,
        "X-Amz-Date": amz_date,
        "X-Amz-Content-Sha256": payload_hash,
    }
    if session_token:
        headers["X-Amz-Security-Token"] = session_token
    if body:
        headers["Content-Type"] = "application/x-amz-json-1.1"
    if extra_headers:
        headers.update(extra_headers)

    signed_header_keys = sorted(k.lower() for k in headers)
    signed_headers = ";".join(signed_header_keys)
    canonical_headers = "".join(
        f"{k}:{headers[{sk: k for sk in signed_header_keys for k in headers if k.lower() == sk}[k]]}\n"
        for k in signed_header_keys
    )

    # Rebuild canonical_headers properly
    header_map = {k.lower(): v for k, v in headers.items()}
    canonical_headers = "".join(f"{k}:{header_map[k]}\n" for k in signed_header_keys)

    canonical_request = "\n".join([
        method, path, canonical_querystring,
        canonical_headers, signed_headers, payload_hash,
    ])

    credential_scope = f"{datestamp}/{AWS_REGION}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, credential_scope, _sha256(canonical_request.encode("utf-8")),
    ])

    signing_key = _hmac_sha256(
        _hmac_sha256(
            _hmac_sha256(
                _hmac_sha256(f"AWS4{secret_key}".encode("utf-8"), datestamp),
                AWS_REGION,
            ),
            service,
        ),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urllib.request.Request(url, data=body if body else None, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# PostgreSQL wire protocol check (startup + simple query, no auth library)
# ---------------------------------------------------------------------------

def _pg_check(host: str, port: int, user: str, database: str) -> None:
    """Verify PostgreSQL accepts connections using the wire protocol.

    Sends a StartupMessage and reads until ReadyForQuery or ErrorResponse.
    Works with md5, scram-sha-256, and trust auth because the server sends
    ReadyForQuery after successful auth negotiation — and for a health check
    we only need to confirm the server is listening and responding.
    For password-protected setups where the server demands auth before
    ReadyForQuery, reaching the Authentication request is proof enough.
    """
    sock = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)
    try:
        # StartupMessage: length(int32) + protocol 3.0 + params
        params = f"user\x00{user}\x00database\x00{database}\x00\x00".encode()
        msg = struct.pack("!II", len(params) + 8, 0x00030000) + params
        sock.sendall(msg)

        # Read at least one response byte — any valid response means PG is alive
        data = sock.recv(1024)
        if not data:
            raise ConnectionError("Empty response from PostgreSQL")
        # First byte is message type: 'R' = Authentication, 'E' = Error
        msg_type = chr(data[0])
        if msg_type == "E":
            # Parse error message for diagnostics
            error_body = data[5:].decode("utf-8", errors="replace").split("\x00")
            raise ConnectionError(f"PostgreSQL error: {error_body}")

        # Terminate gracefully
        sock.sendall(b"X\x00\x00\x00\x04")
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Redis RESP protocol check (PING → +PONG)
# ---------------------------------------------------------------------------

def _redis_check(host: str, port: int, password: str | None, use_ssl: bool) -> None:
    """Verify Redis connectivity using raw RESP protocol."""
    raw_sock = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)
    try:
        if use_ssl:
            import ssl
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(raw_sock, server_hostname=host)
        else:
            sock = raw_sock

        try:
            if password:
                auth_cmd = f"*2\r\n$4\r\nAUTH\r\n${len(password)}\r\n{password}\r\n"
                sock.sendall(auth_cmd.encode())
                auth_resp = sock.recv(256).decode()
                if not auth_resp.startswith("+OK"):
                    raise ConnectionError(f"Redis AUTH failed: {auth_resp.strip()}")

            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            resp = sock.recv(256).decode()
            if "+PONG" not in resp:
                raise ConnectionError(f"Redis unexpected response: {resp.strip()}")
        finally:
            try:
                sock.sendall(b"*1\r\n$4\r\nQUIT\r\n")
            except OSError:
                pass
            if use_ssl:
                sock.close()
    finally:
        raw_sock.close()


# ---------------------------------------------------------------------------
# Health check functions
# ---------------------------------------------------------------------------

def check_database() -> dict:
    host = os.environ.get("POSTGRES_HOST")
    if not host:
        return {"status": "skipped", "reason": "POSTGRES_HOST not configured"}

    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    user = os.environ.get("POSTGRES_USER", "postgres")
    dbname = os.environ.get("POSTGRES_DB", "ai_agent")

    start = time.monotonic()
    try:
        _pg_check(host, port, user, dbname)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms, "type": "aurora-postgresql"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "type": "aurora-postgresql"}


def check_redis() -> dict:
    host = os.environ.get("REDIS_HOST")
    if not host:
        return {"status": "skipped", "reason": "REDIS_HOST not configured"}

    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD")
    use_ssl = os.environ.get("REDIS_SSL", "true").lower() == "true"

    start = time.monotonic()
    try:
        _redis_check(host, port, password, use_ssl)
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_bedrock() -> dict:
    start = time.monotonic()
    try:
        url = f"https://bedrock.{AWS_REGION}.amazonaws.com/foundation-models?byOutputModality=TEXT"
        resp = _sigv4_request("GET", url, "bedrock")
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
    kb_id = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID")
    if not kb_id:
        return {"status": "skipped", "reason": "BEDROCK_KNOWLEDGE_BASE_ID not configured"}

    start = time.monotonic()
    try:
        url = f"https://bedrock-agent.{AWS_REGION}.amazonaws.com/knowledgebases/{kb_id}"
        resp = _sigv4_request("GET", url, "bedrock")
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
    app_url = os.environ.get("MAIN_APP_HEALTH_URL")
    if not app_url:
        return {"status": "skipped", "reason": "MAIN_APP_HEALTH_URL not configured"}

    start = time.monotonic()
    try:
        req = urllib.request.Request(app_url, method="GET")
        with urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT) as resp:
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
    cluster = os.environ.get("ECS_CLUSTER_NAME")
    if not cluster:
        return {"status": "skipped", "reason": "ECS_CLUSTER_NAME not configured"}

    try:
        # ListServices
        url = f"https://ecs.{AWS_REGION}.amazonaws.com/"
        list_body = json.dumps({"cluster": cluster}).encode()
        list_resp = _sigv4_request(
            "POST", url, "ecs", body=list_body,
            extra_headers={"X-Amz-Target": "AmazonEC2ContainerServiceV20141113.ListServices"},
        )
        service_arns = list_resp.get("serviceArns", [])

        if not service_arns:
            return {"status": "unhealthy", "error": "No services found in cluster"}

        # DescribeServices
        desc_body = json.dumps({"cluster": cluster, "services": service_arns}).encode()
        desc_resp = _sigv4_request(
            "POST", url, "ecs", body=desc_body,
            extra_headers={"X-Amz-Target": "AmazonEC2ContainerServiceV20141113.DescribeServices"},
        )

        services = {}
        all_stable = True

        for svc in desc_resp.get("services", []):
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


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

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
    try:
        return name, check_fn()
    except Exception as e:
        return name, {"status": "unhealthy", "error": f"Check crashed: {e}"}


def lambda_handler(event, context):
    raw_path = event.get("rawPath") or event.get("path") or event.get("resource") or ""
    path = raw_path.rstrip("/")
    if path.endswith("/health-check") or path == "health-check":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": DASHBOARD_HTML,
        }

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
