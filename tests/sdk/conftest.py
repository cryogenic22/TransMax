"""Shared fixtures for SDK tests."""

import pytest
from transmax_sdk.config import SDKConfig
from transmax_sdk.container import SDKContainer
from transmax_sdk.telemetry.noop import NoOpTelemetry


@pytest.fixture
def noop_telemetry():
    """NoOp telemetry that records calls for assertions."""
    return NoOpTelemetry(record=True)


@pytest.fixture
def sdk_config():
    """Minimal SDK config for testing (no real API keys)."""
    return SDKConfig(
        openai_api_key="test-key-not-real",
        enable_otel=False,
        enable_prometheus=False,
        database_url=None,
    )


@pytest.fixture
def container(sdk_config, noop_telemetry):
    """DI container wired with test config and NoOp telemetry."""
    return SDKContainer(config=sdk_config, telemetry=noop_telemetry)
