"""Shared Pydantic v2 schema base types.

Feature-specific request/response schemas (patients, studies, reports) are added
in their respective iterations and inherit from `AppModel`.
"""
from pydantic import BaseModel, ConfigDict


class AppModel(BaseModel):
    """Base for API schemas: reads attributes from ORM objects, trims strings."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class HealthStatus(AppModel):
    status: str
    service: str = "teleradiokin-api"
