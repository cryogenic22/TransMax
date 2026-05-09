"""
TMX-3015 — soft-delete primitive.

A model that inherits `SoftDeleteMixin` gets:
  - three columns: `is_deleted` (NOT NULL, default False), `deleted_at`, `deleted_by`
  - a `soft_delete(actor_id)` method that sets the trio
  - a SQLAlchemy `before_delete` event listener that raises `HardDeleteRefused`
    if any caller attempts a hard delete (`session.delete(obj)`)
  - a session-wide `do_orm_execute` event listener that auto-appends
    `WHERE is_deleted = false` to every SELECT against a soft-delete-capable
    model, unless the query is run with `execution_options(include_deleted=True)`

Per CLAUDE.md A9 (soft-delete only): the audit chain must outlive the rows it
references. Hard-delete breaks that invariant. The event listener is the
mechanical enforcement.

A typical migration pattern:

    @router.delete("/things/{thing_id}")
    def delete_thing(thing_id: str, db: Session = Depends(get_db),
                     user = Depends(get_current_user)):
        thing = db.query(Thing).filter_by(id=thing_id).one()
        thing.soft_delete(actor_id=user.user_id)
        db.commit()

The auto-filter then ensures the row stops appearing in normal queries while
remaining recoverable for forensic / admin workflows via:

    db.query(Thing).execution_options(include_deleted=True).filter(...).all()
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, String, event
from sqlalchemy.orm import Session, with_loader_criteria


class HardDeleteRefused(RuntimeError):
    """Raised by SQLAlchemy `before_delete` when a caller attempts to hard-delete
    a tenant-scoped row. Per A9 the only legitimate path is `obj.soft_delete()`."""


class SoftDeleteMixin:
    """Mixin that adds soft-delete columns + behaviour to a SQLAlchemy model."""

    is_deleted = Column(Boolean, nullable=False, default=False, server_default="0")
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(36), nullable=True)

    def soft_delete(self, actor_id: Optional[str] = None) -> None:
        """Mark this row as deleted. Sets `is_deleted=True`, `deleted_at=now`,
        and `deleted_by=actor_id`. The caller is responsible for committing
        the session and emitting any audit event."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = actor_id


@event.listens_for(SoftDeleteMixin, "before_delete", propagate=True)
def _refuse_hard_delete(_mapper, _connection, target):  # noqa: ANN001
    """Refuse `session.delete(obj)` for any model that includes the mixin.

    Callers must use `obj.soft_delete(actor_id)` instead. A regulator or
    auditor reading the codebase can rely on this listener: hard-delete on a
    tenant-scoped row is mechanically impossible.
    """
    raise HardDeleteRefused(
        f"Hard-delete refused on {type(target).__name__}: use "
        f"obj.soft_delete(actor_id) instead. See CLAUDE.md addendum A9."
    )


@event.listens_for(Session, "do_orm_execute")
def _filter_soft_deleted(execute_state) -> None:  # noqa: ANN001
    """Auto-append `WHERE is_deleted = false` to every SELECT against a
    soft-delete-capable model, unless the caller explicitly opts in via
    `execution_options(include_deleted=True)`.

    Forensic / admin workflows that need to see deleted rows pass:
        session.query(Foo).execution_options(include_deleted=True)
    """
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_deleted", False):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.is_deleted == False,  # noqa: E712 — SQLAlchemy needs `==`
            include_aliases=True,
        )
    )
