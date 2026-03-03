"""Tests for DI container."""

import pytest
from transmax_sdk.config import SDKConfig
from transmax_sdk.container import SDKContainer
from transmax_sdk.telemetry.noop import NoOpTelemetry
from transmax_sdk.telemetry.protocol import TelemetryProtocol


class TestSDKContainer:
    def test_default_config(self):
        container = SDKContainer()
        assert container.config is not None
        assert isinstance(container.config, SDKConfig)

    def test_custom_config(self, sdk_config):
        container = SDKContainer(config=sdk_config)
        assert container.config.openai_api_key == "test-key-not-real"

    def test_default_telemetry_is_noop(self):
        container = SDKContainer()
        assert isinstance(container.telemetry, NoOpTelemetry)

    def test_custom_telemetry(self, noop_telemetry):
        container = SDKContainer(telemetry=noop_telemetry)
        assert container.telemetry is noop_telemetry

    def test_noop_satisfies_protocol(self, noop_telemetry):
        assert isinstance(noop_telemetry, TelemetryProtocol)

    def test_register_and_resolve(self, container):
        container.register("my_service", {"key": "value"})
        assert container.resolve("my_service") == {"key": "value"}

    def test_resolve_unknown_raises(self, container):
        with pytest.raises(KeyError, match="No component registered"):
            container.resolve("nonexistent")

    def test_register_factory_lazy(self, container):
        call_count = 0

        def factory(c):
            nonlocal call_count
            call_count += 1
            return "created"

        container.register_factory("lazy_svc", factory)
        assert call_count == 0  # Not yet called

        result = container.resolve("lazy_svc")
        assert result == "created"
        assert call_count == 1

        # Second resolve returns cached
        result2 = container.resolve("lazy_svc")
        assert result2 == "created"
        assert call_count == 1  # Not called again

    def test_has(self, container):
        assert not container.has("foo")
        container.register("foo", 42)
        assert container.has("foo")

    def test_has_factory(self, container):
        container.register_factory("bar", lambda c: 99)
        assert container.has("bar")

    def test_register_overrides_factory(self, container):
        container.register_factory("svc", lambda c: "from_factory")
        container.register("svc", "override")
        assert container.resolve("svc") == "override"

    def test_register_defaults_wires_cost_tracker(self, container):
        container._register_defaults()
        tracker = container.resolve("cost_tracker")
        from transmax_sdk.telemetry.cost import CostTracker
        assert isinstance(tracker, CostTracker)
