"""CloudWatch backend custom metrics tests."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

import app.core.cloudwatch_metrics as cloudwatch_metrics
from app.core.cloudwatch_metrics import (
    BackendErrorRateCollector,
    BackendErrorRateMiddleware,
    BackendErrorRateSnapshot,
    BedrockAgentInvocationSnapshot,
    CloudWatchMetricPublisher,
    publish_bedrock_agent_invocation_metrics,
    schedule_bedrock_agent_invocation_metrics,
)


def test_backend_error_rate_collector_counts_5xx_only():
    collector = BackendErrorRateCollector()

    for status_code in (200, 204, 301, 400, 404, 500, 503):
        collector.record(status_code)

    snapshot = collector.snapshot(reset=True)

    assert snapshot.request_count == 7
    assert snapshot.error_5xx_count == 2
    assert collector.snapshot().request_count == 0


def test_backend_error_rate_collector_excludes_health_and_metrics_paths():
    collector = BackendErrorRateCollector()

    assert not collector.should_record("/metrics")
    assert not collector.should_record("/health")
    assert not collector.should_record("/health/live")
    assert not collector.should_record("/health/ready")
    assert not collector.should_record("/api/v1/health")
    assert not collector.should_record("/api/v1/health/ready")
    assert not collector.should_record("/api/v1/ready")
    assert collector.should_record("/api/v1/conversations")


class FakeCloudWatchClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_metric_data(self, **kwargs) -> None:
        self.calls.append(kwargs)


class FakeBedrockAgentPublisher:
    def __init__(self) -> None:
        self.snapshots: list[BedrockAgentInvocationSnapshot] = []

    def publish_bedrock_agent_invocation(
        self,
        snapshot: BedrockAgentInvocationSnapshot,
    ) -> bool:
        self.snapshots.append(snapshot)
        return True


def test_cloudwatch_publisher_uses_weighted_statistic_values():
    client = FakeCloudWatchClient()
    publisher = CloudWatchMetricPublisher(
        namespace="webapp-group10/backend",
        service_name="backend",
        environment="production",
        client=client,
    )

    published = publisher.publish_backend_error_rate(
        BackendErrorRateSnapshot(request_count=100, error_5xx_count=5)
    )

    assert published is True
    metric = client.calls[0]["MetricData"][0]
    assert client.calls[0]["Namespace"] == "webapp-group10/backend"
    assert metric["MetricName"] == "BackendErrorRate"
    assert metric["Unit"] == "Percent"
    assert metric["StatisticValues"] == {
        "SampleCount": 100.0,
        "Sum": 500.0,
        "Minimum": 0.0,
        "Maximum": 100.0,
    }
    assert {"Name": "Environment", "Value": "production"} in metric["Dimensions"]
    assert {"Name": "Service", "Value": "backend"} in metric["Dimensions"]


def test_cloudwatch_publisher_skips_empty_window():
    client = FakeCloudWatchClient()
    publisher = CloudWatchMetricPublisher(
        namespace="webapp-group10/backend",
        service_name="backend",
        environment="production",
        client=client,
    )

    published = publisher.publish_backend_error_rate(
        BackendErrorRateSnapshot(request_count=0, error_5xx_count=0)
    )

    assert published is False
    assert client.calls == []


def test_cloudwatch_publisher_publishes_bedrock_invocation_count_and_latency():
    client = FakeCloudWatchClient()
    publisher = CloudWatchMetricPublisher(
        namespace="webapp-group10/backend",
        service_name="backend",
        environment="production",
        client=client,
    )
    timestamp = datetime(2026, 5, 21, tzinfo=UTC)

    published = publisher.publish_bedrock_agent_invocation(
        BedrockAgentInvocationSnapshot(
            latency_ms=1234.5,
            model_name="us.anthropic.claude-sonnet-4-20250514",
            operation="agent_stream",
            timestamp=timestamp,
        )
    )

    assert published is True
    assert client.calls[0]["Namespace"] == "webapp-group10/backend"
    metrics = client.calls[0]["MetricData"]
    assert [metric["MetricName"] for metric in metrics] == [
        "bedrock_agent_invocation_count",
        "bedrock_agent_latency_ms",
    ]
    assert [metric["Value"] for metric in metrics] == [1.0, 1234.5]
    assert [metric["Unit"] for metric in metrics] == ["Count", "Milliseconds"]
    for metric in metrics:
        assert metric["Timestamp"] == timestamp
        assert {"Name": "Environment", "Value": "production"} in metric["Dimensions"]
        assert {"Name": "Service", "Value": "backend"} in metric["Dimensions"]
        assert {
            "Name": "Model",
            "Value": "us.anthropic.claude-sonnet-4-20250514",
        } in metric["Dimensions"]
        assert {"Name": "Operation", "Value": "agent_stream"} in metric["Dimensions"]


@pytest.mark.anyio
async def test_publish_bedrock_agent_invocation_metrics_publishes_snapshot():
    publisher = FakeBedrockAgentPublisher()

    published = await publish_bedrock_agent_invocation_metrics(
        latency_ms=42.25,
        operation="image_description",
        model_name="fallback-model",
        publisher=publisher,
    )

    assert published is True
    assert publisher.snapshots[0].latency_ms == 42.25
    assert publisher.snapshots[0].model_name == "fallback-model"
    assert publisher.snapshots[0].operation == "image_description"


@pytest.mark.anyio
async def test_schedule_bedrock_metrics_does_not_block_agent_path(monkeypatch):
    monkeypatch.setattr(cloudwatch_metrics.settings, "CLOUDWATCH_METRICS_ENABLED", True)
    started = asyncio.Event()

    async def slow_publish(**kwargs: Any) -> bool:
        started.set()
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(
        cloudwatch_metrics,
        "publish_bedrock_agent_invocation_metrics",
        slow_publish,
    )

    schedule_bedrock_agent_invocation_metrics(
        latency_ms=10,
        operation="agent_stream",
        model_name="test-model",
    )

    await asyncio.wait_for(started.wait(), timeout=1)


@pytest.mark.anyio
async def test_backend_error_rate_middleware_records_completed_requests():
    collector = BackendErrorRateCollector(excluded_paths={"/metrics"})
    app = FastAPI()
    app.add_middleware(BackendErrorRateMiddleware, collector=collector)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/fail")
    async def fail() -> Response:
        return Response(status_code=500)

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(status_code=500)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/ok")
        await client.get("/fail")
        await client.get("/metrics")

    snapshot = collector.snapshot()

    assert snapshot.request_count == 2
    assert snapshot.error_5xx_count == 1
