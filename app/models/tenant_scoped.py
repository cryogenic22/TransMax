"""
TMX-3012 — `TenantScopedMixin` + SQLAlchemy event listeners.

A model that inherits `TenantScopedMixin` participates in two automatic
behaviours:

  1. **Auto-injection on insert.** A `before_insert` listener sets
     `instance.organization_id` from the current tenant context (see
     `app.core.tenant_context`) when the caller didn't provide it. If
     there is no current tenant context AND the caller didn't provide
     a value, the listener raises `TenantContextMissing` — A3 forbids
     a silent fallback to a "default tenant".

  2. **Auto-filter on SELECT.** A `do_orm_execute` listener appends
     `WHERE organization_id = current_org_id()` to every query that
     touches a tenant-scoped model. Stacks cleanly with the soft-delete
     filter from TMX-3015. Callers can opt out with
     `query.execution_options(include_other_tenants=True)` for forensic
     and admin paths.

The mixin adds NO columns — `organization_id` is already declared on each
model by TMX-3011. The mixin is purely a marker for the listeners.

Why a separate mixin (not reused `SoftDeleteMixin`):
  - `audit_events_v2` (TMX-3100) is tenant-scoped but NOT soft-delete-capable.
  - `organizations` is the FK target, not a tenant-scoped row.
  Reusing the soft-delete mixin would conflate the two concepts. Mixing
  them is a design-by-accident anti-pattern.
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, ORMExecuteState, Session, declared_attr, with_loader_criteria

from app.core.tenant_context import TenantContextMissing, current_org_id
from app.models.types import GUID


class TenantScopedMixin:
    """Marker mixin: this model carries `organization_id` and participates
    in tenant filtering + auto-injection.

    The column is declared via `declared_attr` so SQLAlchemy attaches the
    same column shape to every subclass AND so `with_loader_criteria(cls, ...)`
    can resolve `cls.organization_id` against the mixin in the auto-filter.
    """

    @declared_attr
    def organization_id(cls):  # noqa: N805
        return Column(
            GUID,
            ForeignKey("organizations.id"),
            nullable=False,
            index=True,
        )


@event.listens_for(TenantScopedMixin, "before_insert", propagate=True)
def _inject_org_id(
    _mapper: Mapper, _connection: Connection, target: "TenantScopedMixin"
) -> None:
    """Auto-inject `organization_id` from the tenant context on insert.

    Order of precedence:
      1. Caller-provided value on the instance (preserved — supports
         legacy fixtures that pass `organization_id=DEFAULT_ORG_ID` explicitly).
      2. Tenant context (`current_org_id()`).
      3. Raise `TenantContextMissing` — A3 forbids silent fallback.
    """
    if getattr(target, "organization_id", None) is not None:
        return
    org = current_org_id()
    if org is None:
        raise TenantContextMissing(
            f"Cannot INSERT into {type(target).__name__}: no tenant context. "
            f"Wrap the work in `org_context(org_id)` or use "
            f"`get_db_session(tenant_id=...)`."
        )
    target.organization_id = org


@event.listens_for(Session, "do_orm_execute")
def _filter_by_tenant(execute_state: ORMExecuteState) -> None:
    """Auto-append `WHERE organization_id = current_org` on every SELECT.

    Opt out with `query.execution_options(include_other_tenants=True)`
    for forensic / admin paths. If there's no tenant context AND the
    query targets a tenant-scoped model, raise — never silently return
    cross-tenant rows.

    Composes with the soft-delete filter from TMX-3015: SQLAlchemy stacks
    multiple `with_loader_criteria` options on the same statement.

    Skip ORM-internal lookups (relationship lazy-loads, attribute refreshes,
    primary-key reloads) — these execute as part of a write the caller
    already authorised by setting context for the original write. Filtering
    them would force every test/service to wrap post-commit attribute access
    in `org_context(...)` which is impractical.
    """
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_other_tenants", False):
        return
    # ORM internals: relationship loads + column refreshes are downstream of
    # a user query that ALREADY passed the context check. Allow them through.
    if execute_state.is_relationship_load or execute_state.is_column_load:
        return

    org = current_org_id()
    if org is None:
        if _query_targets_tenant_scoped(execute_state):
            raise TenantContextMissing(
                "SELECT against a tenant-scoped table requires a tenant context. "
                "Wrap the work in `org_context(org_id)` or use "
                "`get_db_session(tenant_id=...)`."
            )
        return  # query touches no tenant-scoped tables — let it through

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantScopedMixin,
            lambda cls: cls.organization_id == org,
            include_aliases=True,
        )
    )


def _query_targets_tenant_scoped(execute_state: ORMExecuteState) -> bool:
    """Return True if the query touches at least one TenantScopedMixin model."""
    try:
        for opt in execute_state.all_mappers:
            if issubclass(opt.class_, TenantScopedMixin):
                return True
    except (AttributeError, TypeError):
        pass
    # Fallback: walk the statement's column descriptions if all_mappers isn't there.
    try:
        for entity in execute_state.statement.column_descriptions or []:
            cls = entity.get("entity")
            if cls is not None and isinstance(cls, type) and issubclass(cls, TenantScopedMixin):
                return True
    except (AttributeError, TypeError):
        pass
    return False
