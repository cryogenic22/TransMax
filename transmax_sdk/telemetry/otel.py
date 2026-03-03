"""OpenTelemetry-based telemetry implementation."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger("transmax_sdk.telemetry")


class OpenTelemetryService:
    """Telemetry backed by OpenTelemetry traces and structured JSON logging.

    Falls back gracefully if OTel SDK is not installed.
    """

    def __init__(self, service_name: str = "transmax-sdk", endpoint: Optional[str] = None) -> None:
        self._service_name = service_name
        self._tracer = None
        self._setup_otel(endpoint)

    def _setup_otel(self, endpoint: Optional[str]) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": self._service_name})
            provider = TracerProvider(resource=resource)

            if endpoint:
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                exporter = OTLPSpanExporter(endpoint=endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))

            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer("transmax_sdk")
        except ImportError:
            logger.warning("OpenTelemetry SDK not installed; spans will be no-ops")
            self._tracer = None

    @contextmanager
    def span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Generator[None, None, None]:
        if self._tracer:
            with self._tracer.start_as_current_span(name, attributes=attributes or {}):
                yield
        else:
            yield

    def counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        self.log_structured("metric", f"counter:{name}", value=value, labels=labels or {})

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        self.log_structured("metric", f"histogram:{name}", value=value, labels=labels or {})

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        self.log_structured("metric", f"gauge:{name}", value=value, labels=labels or {})

    def log_structured(self, level: str, message: str, **kwargs: Any) -> None:
        entry = {
            "ts": time.time(),
            "level": level,
            "service": self._service_name,
            "msg": message,
            **kwargs,
        }
        logger.info(json.dumps(entry, default=str))
