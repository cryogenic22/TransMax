"""
TMX-WEBHOOK-FIRE — terminal-status webhook dispatch for the v1 job path.

`JobCreateRequest.webhook_url` used to be accepted and silently ignored: an
integrator who registered a callback got neither a call nor an error — a
silent failure in a regulated path (A3). This module is the single outbound
delivery path, and `is_private_webhook_host` is the single source of truth
for the SSRF host predicate the schema validator enforces (no fork).

Contract
--------

`dispatch_job_webhook` runs as a FastAPI background task scheduled AFTER
`run_pipeline_background` — Starlette executes `BackgroundTasks` strictly in
order, so by the time it runs the job has reached its terminal state. It:

1. re-reads the job's terminal status from the DB (A3: report what IS; if
   the row is missing, abort loudly — never POST a fabricated status);
2. emits a `WEBHOOK_DISPATCH_ATTEMPTED` v2 audit event BEFORE the outbound
   side effect (A1 ordering);
3. POSTs ``{job_id, status, request_id, timestamp}`` to the integrator URL
   (timeout 10s, 3 attempts, exponential backoff, redirects NOT followed —
   a public receiver 30x-ing to an internal IP must not be chased);
4. emits `WEBHOOK_DELIVERED` on success (positive assertion on the chain —
   absence-of-failure is not evidence), or `WEBHOOK_DELIVERY_FAILED` +
   `logger.warning` on exhaustion.

Failure containment: delivery failure NEVER raises out of the background
path. The job is already terminal; a flaky receiver must not corrupt its
state. This is a controlled, documented containment (same posture as
`app/agents/_audit_v2_emit.py`), not a silent fallback — every failure is
surfaced via WARNING log + audit event.
"""

from __future__ import annotations

import ipaddress
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.agents._audit_v2_emit import emit_v2_audit_event
from app.core.tenant_context import TenantContextMissing, org_context

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS: float = 10.0
WEBHOOK_MAX_ATTEMPTS: int = 3
# Sleep between attempts: base * 2^(attempt-1) → 1s, 2s. Tests patch to 0.
WEBHOOK_BACKOFF_BASE_SECONDS: float = 1.0


def is_private_webhook_host(host: str) -> bool:
    """True when `host` is a loopback / private-range / link-local target.

    Pure literal check (no DNS resolution): covers ``localhost`` (and
    ``*.localhost``), 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12,
    192.168.0.0/16, 169.254.0.0/16, 0.0.0.0, and the IPv6 equivalents
    (::1, fc00::/7, fe80::/10, ::). A public DNS name that *resolves* to a
    private IP (DNS rebinding) is explicitly out of scope — recorded in the
    TMX-WEBHOOK-FIRE worksheet, stage 6.
    """
    normalized = host.strip().lower().rstrip(".")
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        addr = ipaddress.ip_address(normalized.strip("[]"))
    except ValueError:
        return False  # not an IP literal ⇒ public hostname (see docstring)
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_unspecified
        or addr.is_multicast
        or addr.is_reserved
    )


def _build_client() -> httpx.Client:
    """Factory seam for the outbound client (tests inject a MockTransport).

    `follow_redirects=False` is load-bearing SSRF hygiene: the request
    validator only vets the host the integrator declared, so a redirect to
    an unvetted (possibly internal) host must not be followed.
    """
    return httpx.Client(timeout=WEBHOOK_TIMEOUT_SECONDS, follow_redirects=False)


def _read_terminal_status(job_id: str) -> Optional[str]:
    """Read the job's current (terminal) status from the DB, or None if the
    row is missing. Resolves `SessionLocal` at call time so the test
    fixture's in-place engine swap is honoured (same reason as
    `_audit_v2_emit._session_factory`)."""
    import app.core.database as core_db
    from app.models.database import Document

    session = core_db.SessionLocal()
    try:
        doc = session.query(Document).filter(Document.id == job_id).first()
        if doc is None:
            return None
        status = doc.status
        return status.value if hasattr(status, "value") else str(status)
    finally:
        session.close()


def dispatch_job_webhook(
    job_id: str,
    webhook_url: str,
    request_id: str,
    *,
    org_id: Optional[str],
) -> None:
    """Deliver the terminal-status callback for `job_id` to `webhook_url`.

    Never raises: the job is already terminal and its state must not be
    affected by receiver behaviour. See module docstring for the A3
    containment justification (WARNING + audit event, never silence).
    """
    try:
        if org_id is None:
            # Mirrors run_pipeline_background's strictness: no default tenant.
            raise TenantContextMissing(
                "webhook dispatch requires a tenant context (org_id is None)"
            )
        with org_context(org_id):
            _dispatch(job_id=job_id, webhook_url=webhook_url, request_id=request_id)
    except (
        Exception
    ) as exc:  # noqa: BLE001 — documented containment, see module docstring
        logger.warning(
            "webhook dispatch aborted (job_id=%s, url=%s): %s",
            job_id,
            webhook_url,
            exc,
        )


def _dispatch(*, job_id: str, webhook_url: str, request_id: str) -> None:
    status = _read_terminal_status(job_id)
    if status is None:
        # A3: never POST a fabricated status for a job we cannot find.
        logger.warning(
            "webhook dispatch aborted: job %s not found — refusing to POST "
            "a fabricated status (A3)",
            job_id,
        )
        emit_v2_audit_event(
            job_id=job_id,
            event_type="WEBHOOK_DELIVERY_FAILED",
            actor_id=None,
            actor_kind="system",
            payload={
                "webhook_url": webhook_url,
                "request_id": request_id,
                "attempts": 0,
                "last_error": "job_row_not_found",
            },
        )
        return

    callback_payload = {
        "job_id": job_id,
        "status": status,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # A1: the audit event precedes the outbound side effect.
    emit_v2_audit_event(
        job_id=job_id,
        event_type="WEBHOOK_DISPATCH_ATTEMPTED",
        actor_id=None,
        actor_kind="system",
        payload={
            "webhook_url": webhook_url,
            "max_attempts": WEBHOOK_MAX_ATTEMPTS,
            "callback_payload": callback_payload,
        },
    )

    last_error = ""
    for attempt in range(1, WEBHOOK_MAX_ATTEMPTS + 1):
        try:
            with _build_client() as client:
                response = client.post(webhook_url, json=callback_payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "webhook attempt %d/%d failed (job_id=%s, url=%s): %s",
                attempt,
                WEBHOOK_MAX_ATTEMPTS,
                job_id,
                webhook_url,
                last_error,
            )
            if attempt < WEBHOOK_MAX_ATTEMPTS:
                time.sleep(WEBHOOK_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
            continue
        emit_v2_audit_event(
            job_id=job_id,
            event_type="WEBHOOK_DELIVERED",
            actor_id=None,
            actor_kind="system",
            payload={
                "webhook_url": webhook_url,
                "attempt": attempt,
                "response_status_code": response.status_code,
            },
        )
        logger.info(
            "webhook delivered (job_id=%s, url=%s, attempt=%d, status=%d)",
            job_id,
            webhook_url,
            attempt,
            response.status_code,
        )
        return

    emit_v2_audit_event(
        job_id=job_id,
        event_type="WEBHOOK_DELIVERY_FAILED",
        actor_id=None,
        actor_kind="system",
        payload={
            "webhook_url": webhook_url,
            "request_id": request_id,
            "attempts": WEBHOOK_MAX_ATTEMPTS,
            "last_error": last_error,
        },
    )
    logger.warning(
        "webhook delivery FAILED after %d attempts (job_id=%s, url=%s): %s "
        "— job state unaffected",
        WEBHOOK_MAX_ATTEMPTS,
        job_id,
        webhook_url,
        last_error,
    )
