"""Shared column types.

`JsonB` is JSONB on PostgreSQL (indexable, binary) and falls back to generic JSON
on other dialects (e.g. SQLite in tests), so the same models work everywhere.
"""
from enum import Enum as PyEnum

from sqlalchemy import JSON, Enum
from sqlalchemy.dialects.postgresql import JSONB

# Use JSONB on PostgreSQL, plain JSON elsewhere.
JsonB = JSON().with_variant(JSONB(), "postgresql")


def str_enum(enum_cls: type[PyEnum], length: int = 32) -> Enum:
    """A non-native string-backed SQLAlchemy Enum column type.

    Stores the enum *value* (e.g. ``"Admin"``) as a portable VARCHAR with a
    length cap, rather than a database-native enum, so the same models run on
    PostgreSQL and SQLite and so values can evolve without a DB enum migration.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )
