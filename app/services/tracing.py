"""
OpenTelemetry tracing scaffolding for TransMax.

Per plan E9 + addendum A6: every LangGraph node emits a span so we can
trace where a job spent its time without parsing free-form logs. Spans
join to audit events via the `job_id` attribute.

Activation:
  Set TRANSMAX_OTEL_ENABLED=1 in the environment to turn on real span
  emission via opentelemetry. Without that env var, `traced(...)` is a
  no-op decorator so test + dev runs pay zero overhead.

Production deploy supplies OTLP exporter config via the standard OTel
environment variables (OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_RESOURCE_ATTRIBUTES,
etc.) — this module does NOT hard-code an exporter URL.

See TMX-3900 worksheet for spec; sister tickets:
  - TMX-3901: LLM-call child spans with prompt_version + content_hash
  - TMX-3902: OTLP exporter config in deployment manifests
"""
from __future__ import annotations

import asyncio
import functools
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_OTEL_ENABLED_FLAG = "TRANSMAX_OTEL_ENABLED"
_initialized = False
_tracer = None  # opentelemetry tracer or None when disabled


def _is_enabled() -> bool:
    return os.environ.get(_OTEL_ENABLED_FLAG, "").lower() in ("1", "true", "yes")


def init_tracing(service_name: str = "transmax") -> None:
    """
    Idempotent setup of the OpenTelemetry TracerProvider.

    No-op when TRANSMAX_OTEL_ENABLED is unset. Safe to call multiple times;
    only the first call configures the provider.
    """
    global _initialized, _tracer
    if _initialized:
        return
    _initialized = True

    if not _is_enabled():
        # Leave _tracer = None; get_tracer() returns the OTel default which
        # is a NoOpTracer when no provider has been set.
        logger.debug("OTel disabled (set TRANSMAX_OTEL_ENABLED=1 to enable).")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError as exc:
        logger.warning(
            "TRANSMAX_OTEL_ENABLED=1 but opentelemetry import failed: %s. "
            "Falling back to no-op tracer.",
            exc,
        )
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    # Console exporter by default — production overrides via OTEL_EXPORTER_*
    # env vars consumed by the otel auto-instrumentation entry point.
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    logger.info("OTel tracing initialised for service=%s", service_name)


def get_tracer(name: str = "transmax"):
    """
    Return a tracer. When OTel is disabled this returns OTel's NoOpTracer
    (a real object whose spans are no-ops) so caller code is identical
    regardless of activation.
    """
    if not _initialized:
        init_tracing()
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return _NullTracer()


class _NullTracer:
    """Used only if `opentelemetry` itself is uninstallable. Tests don't hit this."""

    def start_as_current_span(self, *_args, **_kwargs):
        return _NullSpanCM()


class _NullSpanCM:
    def __enter__(self):
        return _NullSpan()

    def __exit__(self, *_):
        return False


class _NullSpan:
    def set_attribute(self, *_args, **_kwargs):
        pass

    def record_exception(self, *_args, **_kwargs):
        pass

    def set_status(self, *_args, **_kwargs):
        pass


def traced(span_name: Optional[str] = None) -> Callable:
    """
    Decorator that wraps a function in an OTel span.

    Supports both sync and async callables. The span name defaults to
    `<module>.<func>` when not provided. If the wrapped function takes
    a TransMax `state: TypedDict` first argument, `job_id` is captured
    on the span as the audit-chain join key.

    Exceptions are recorded on the span and re-raised — the decorator
    never swallows.
    """

    def decorator(fn):
        name = span_name or f"{fn.__module__}.{fn.__qualname__}"

        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.start_as_current_span(name) as span:
                    _attach_job_id(span, args, kwargs)
                    try:
                        return await fn(*args, **kwargs)
                    except Exception as exc:
                        span.record_exception(exc)
                        raise
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                _attach_job_id(span, args, kwargs)
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    raise

        return sync_wrapper

    return decorator


def _attach_job_id(span, args, kwargs):
    """If the first positional arg looks like TransMax state, record job_id."""
    state = args[0] if args else kwargs.get("state")
    if not isinstance(state, dict):
        return
    job_id = state.get("job_id")
    if job_id is not None:
        span.set_attribute("transmax.job_id", str(job_id))
    doc_id = state.get("doc_id")
    if doc_id is not None:
        span.set_attribute("transmax.doc_id", str(doc_id))
