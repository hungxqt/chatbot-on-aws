"""CloudWatch custom metrics for backend runtime health."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

import boto3
from botocore.config import Config
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)

CLOUDWATCH_CLIENT_CONFIG = Config(
    connect_timeout=1,
    read_timeout=1,
    retries={"max_attempts": 2, "mode": "standard"},
)
CLOUDWATCH_PUBLISH_TIMEOUT_SECONDS = 2.0


DEFAULT_EXCLUDED_PATHS = {
    settings.PROMETHEUS_METRICS_PATH,
    "/health",
    "/health/live",
    "/health/ready",
}
DEFAULT_EXCLUDED_PREFIXES = (
    f"{settings.API_V1_STR}/health",
    f"{settings.API_V1_STR}/ready",
)


@dataclass(frozen=True)
class BackendErrorRateSnapshot:
    """Aggregated backend request counters for one CloudWatch publish window."""

    request_count: int
    error_5xx_count: int


@dataclass(frozen=True)
class BedrockAgentInvocationSnapshot:
    """Invocation metrics from one completed Bedrock agent call."""

    latency_ms: float
    model_name: str
    operation: str
    timestamp: datetime


class BackendErrorRateCollector:
    """Thread-safe request/error counter for backend HTTP responses."""

    def __init__(
        self,
        excluded_paths: set[str] | None = None,
        excluded_prefixes: tuple[str, ...] | None = None,
    ) -> None:
        self._lock = Lock()
        self._request_count = 0
        self._error_5xx_count = 0
        self._excluded_paths = excluded_paths or DEFAULT_EXCLUDED_PATHS
        self._excluded_prefixes = excluded_prefixes or DEFAULT_EXCLUDED_PREFIXES

    def should_record(self, path: str) -> bool:
        """Return whether a request path should contribute to backend error rate."""
        if path in self._excluded_paths:
            return False
        return not any(path.startswith(prefix) for prefix in self._excluded_prefixes)

    def record(self, status_code: int) -> None:
        """Record a completed HTTP response."""
        with self._lock:
            self._request_count += 1
            if status_code >= 500:
                self._error_5xx_count += 1

    def snapshot(self, reset: bool = False) -> BackendErrorRateSnapshot:
        """Return the current counters, optionally resetting the window."""
        with self._lock:
            snapshot = BackendErrorRateSnapshot(
                request_count=self._request_count,
                error_5xx_count=self._error_5xx_count,
            )
            if reset:
                self._request_count = 0
                self._error_5xx_count = 0
            return snapshot


class BackendErrorRateMiddleware(BaseHTTPMiddleware):
    """Record request status codes for CloudWatch backend error-rate metrics."""

    def __init__(self, app: ASGIApp, collector: BackendErrorRateCollector) -> None:
        super().__init__(app)
        self._collector = collector

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if self._collector.should_record(request.url.path):
            self._collector.record(response.status_code)
        return response


class CloudWatchMetricPublisher:
    """Publish backend metrics to CloudWatch."""

    def __init__(
        self,
        namespace: str,
        service_name: str,
        environment: str,
        client: Any | None = None,
    ) -> None:
        self._namespace = namespace
        self._service_name = service_name
        self._environment = environment
        self._client = client or boto3.client(
            "cloudwatch",
            region_name=settings.AWS_REGION,
            config=CLOUDWATCH_CLIENT_CONFIG,
        )

    def publish_backend_error_rate(self, snapshot: BackendErrorRateSnapshot) -> bool:
        """Publish BackendErrorRate as a weighted Percent metric."""
        if snapshot.request_count <= 0:
            return False

        metric_value_sum = float(snapshot.error_5xx_count * 100)
        min_value = 100.0 if snapshot.error_5xx_count == snapshot.request_count else 0.0
        max_value = 100.0 if snapshot.error_5xx_count > 0 else 0.0

        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {
                    "MetricName": "BackendErrorRate",
                    "Dimensions": [
                        {"Name": "Environment", "Value": self._environment},
                        {"Name": "Service", "Value": self._service_name},
                    ],
                    "Timestamp": datetime.now(UTC),
                    "Unit": "Percent",
                    "StatisticValues": {
                        "SampleCount": float(snapshot.request_count),
                        "Sum": metric_value_sum,
                        "Minimum": min_value,
                        "Maximum": max_value,
                    },
                }
            ],
        )
        return True

    def publish_bedrock_agent_invocation(
        self,
        snapshot: BedrockAgentInvocationSnapshot,
    ) -> bool:
        """Publish invocation count and latency for one Bedrock agent call."""
        if snapshot.latency_ms < 0:
            return False

        dimensions = [
            {"Name": "Environment", "Value": self._environment},
            {"Name": "Service", "Value": self._service_name},
            {"Name": "Model", "Value": snapshot.model_name},
            {"Name": "Operation", "Value": snapshot.operation},
        ]

        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {
                    "MetricName": "bedrock_agent_invocation_count",
                    "Dimensions": dimensions,
                    "Timestamp": snapshot.timestamp,
                    "Unit": "Count",
                    "Value": 1.0,
                },
                {
                    "MetricName": "bedrock_agent_latency_ms",
                    "Dimensions": dimensions,
                    "Timestamp": snapshot.timestamp,
                    "Unit": "Milliseconds",
                    "Value": float(snapshot.latency_ms),
                },
            ],
        )
        return True


backend_error_rate_collector = BackendErrorRateCollector()


async def run_cloudwatch_metrics_publisher(
    collector: BackendErrorRateCollector = backend_error_rate_collector,
) -> None:
    """Periodically publish backend metrics until cancelled."""
    publisher = CloudWatchMetricPublisher(
        namespace=settings.CLOUDWATCH_METRICS_NAMESPACE,
        service_name=settings.CLOUDWATCH_METRICS_SERVICE_NAME,
        environment=settings.ENVIRONMENT,
    )
    interval_seconds = max(1, settings.CLOUDWATCH_METRICS_INTERVAL_SECONDS)

    while True:
        await asyncio.sleep(interval_seconds)
        snapshot = collector.snapshot(reset=True)
        try:
            published = await asyncio.to_thread(publisher.publish_backend_error_rate, snapshot)
            if published:
                logger.debug("Published BackendErrorRate to CloudWatch: %s", snapshot)
        except Exception:
            logger.exception("Failed to publish BackendErrorRate to CloudWatch")


async def publish_bedrock_agent_invocation_metrics(
    latency_ms: float,
    operation: str,
    model_name: str | None = None,
    publisher: CloudWatchMetricPublisher | None = None,
) -> bool:
    """Publish Bedrock agent invocation count and latency metrics."""
    if publisher is None and not settings.CLOUDWATCH_METRICS_ENABLED:
        return False

    metric_publisher = publisher or CloudWatchMetricPublisher(
        namespace=settings.CLOUDWATCH_METRICS_NAMESPACE,
        service_name=settings.CLOUDWATCH_METRICS_SERVICE_NAME,
        environment=settings.ENVIRONMENT,
    )
    snapshot = BedrockAgentInvocationSnapshot(
        latency_ms=max(0.0, float(latency_ms)),
        model_name=model_name or "unknown",
        operation=operation,
        timestamp=datetime.now(UTC),
    )

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(metric_publisher.publish_bedrock_agent_invocation, snapshot),
            timeout=CLOUDWATCH_PUBLISH_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning("Timed out publishing Bedrock agent invocation metrics to CloudWatch")
        return False
    except Exception:
        logger.exception("Failed to publish Bedrock agent invocation metrics to CloudWatch")
        return False


def schedule_bedrock_agent_invocation_metrics(
    latency_ms: float,
    operation: str,
    model_name: str | None = None,
) -> None:
    """Schedule Bedrock agent metrics without blocking the agent response path."""
    if not settings.CLOUDWATCH_METRICS_ENABLED:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("Skipping Bedrock metrics publish because no event loop is running")
        return

    task = loop.create_task(
        publish_bedrock_agent_invocation_metrics(
            latency_ms=latency_ms,
            operation=operation,
            model_name=model_name,
        )
    )
    task.add_done_callback(_log_bedrock_metrics_task_result)


def _log_bedrock_metrics_task_result(task: asyncio.Task[bool]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.debug("Bedrock metrics publish task was cancelled")
    except Exception:
        logger.exception("Bedrock metrics publish task failed unexpectedly")
