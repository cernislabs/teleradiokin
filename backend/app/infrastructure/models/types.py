"""Shared column types.

`JsonB` is JSONB on PostgreSQL (indexable, binary) and falls back to generic JSON
on other dialects (e.g. SQLite in tests), so the same models work everywhere.
"""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Use JSONB on PostgreSQL, plain JSON elsewhere.
JsonB = JSON().with_variant(JSONB(), "postgresql")
