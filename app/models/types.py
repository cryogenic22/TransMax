"""
Portable column type decorators shared across the operational (database.py)
and regulatory (translation.py) layers.

`GUID` resolves to a native `UUID` on PostgreSQL and `CHAR(36)` on SQLite.
This bridges the two model layers (A4) so that a single `organizations.id`
primary key is FK-compatible with both `String(36)` IDs (database.py) and
`UUID(as_uuid=True)` IDs (translation.py).

UUID values are stored as their canonical 36-character string form on SQLite,
and as native UUID values on Postgres. The decorator normalises both to
strings on the way out so callers can compare with string-typed columns.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine


class GUID(TypeDecorator):
    """Cross-dialect GUID type. Stores values as 36-character strings."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
        self, value: Optional[object], dialect: Dialect
    ) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(
        self, value: Optional[object], dialect: Dialect
    ) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)
