"""Shared Pydantic v2 schema base types.

Feature-specific request/response schemas (patients, studies, reports) are added
in their respective iterations and inherit from `AppModel`.
"""
import json

from pydantic import BaseModel, ConfigDict

# Cap on client-supplied extensible JSONB blobs (`extra`) to prevent a caller
# stuffing arbitrarily large documents into every record.
MAX_EXTRA_BYTES = 16 * 1024


class AppModel(BaseModel):
    """Base for API schemas: reads attributes from ORM objects, trims strings."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


def bounded_extra(value: dict | None) -> dict | None:
    """Validator helper: reject an `extra` blob larger than MAX_EXTRA_BYTES."""
    if value is None:
        return value
    if len(json.dumps(value, default=str).encode("utf-8")) > MAX_EXTRA_BYTES:
        raise ValueError(f"'extra' exceeds the maximum of {MAX_EXTRA_BYTES} bytes")
    return value


class HealthStatus(AppModel):
    status: str
    service: str = "teleradiokin-api"
