"""
TMX-3012 — request-scoped tenant context.

A `ContextVar` holds the current tenant id (`organization_id`) for the
duration of a request or work unit. The SQLAlchemy listeners in
`app.models.tenant_scoped` read this to:
  - inject `organization_id` on insert (A1: every row provably belongs to a tenant)
  - filter SELECTs by `organization_id` (per-tenant data isolation)

Storage uses `contextvars.ContextVar`, not `threading.local`, so it works
correctly under FastAPI / asyncio (per-task scoping).

Usage:

    from app.core.tenant_context import org_context, current_org_id

    with org_context("acme-pharma-uuid"):
        ...                     # any DB ops in here are scoped to acme
        do_some_work()
    # context cleared on exit

In FastAPI:

    @router.get("/things")
    def list_things(db = Depends(get_tenant_session)):
        return db.query(Thing).all()  # auto-filtered by current tenant

When there's no context, callers that touch tenant-scoped tables raise
`TenantContextMissing`. Per A3 (no silent fallbacks): there is no
"default tenant" fallback at this layer.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional


class TenantContextMissing(RuntimeError):
    """Raised when a tenant-scoped DB op runs with no current tenant.

    Callers must wrap the work in `org_context(org_id)` or
    `get_db_session(tenant_id=...)`. See CLAUDE.md A3.
    """


_current_org: ContextVar[Optional[str]] = ContextVar(
    "transmax_current_org_id", default=None
)


def current_org_id() -> Optional[str]:
    """Return the current tenant id, or None if no context is active."""
    return _current_org.get()


def set_org_id(org_id: Optional[str]) -> Token:
    """Set the current tenant id and return a Token for later reset."""
    return _current_org.set(org_id)


def clear_org(token: Token) -> None:
    """Reset the tenant id to its prior value (or None)."""
    _current_org.reset(token)


@contextmanager
def org_context(org_id: str) -> Iterator[None]:
    """Set the current tenant id for the duration of the with-block.

    On exit, restores whatever the prior value was (typically None, but
    nested contexts compose correctly).
    """
    if org_id is None:
        raise ValueError("org_context(None) is not allowed; use clear_org() to unset.")
    token = set_org_id(org_id)
    try:
        yield
    finally:
        clear_org(token)
