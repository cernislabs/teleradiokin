"""Core domain enumerations (no persistence or framework dependencies)."""
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "Admin"
    REFERRING_CLINICIAN = "ReferringClinician"
    RADIOLOGIST = "Radiologist"


class StudyStatus(StrEnum):
    """Lifecycle of an imaging study through the worklist."""

    UPLOADING = "Uploading"       # chunks still arriving
    PROCESSING = "Processing"     # background metadata/preview extraction
    PENDING = "Pending"           # ready, awaiting radiologist
    IN_REVIEW = "InReview"
    REPORTED = "Reported"
    FAILED = "Failed"


class ReportStatus(StrEnum):
    DRAFT = "Draft"
    FINAL = "Final"


class AdministrativeGender(StrEnum):
    """FHIR administrative gender."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class EncounterStatus(StrEnum):
    """Simplified FHIR Encounter status."""

    PLANNED = "planned"
    IN_PROGRESS = "in-progress"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class AuditAction(StrEnum):
    """What a recorded audit event represents (FHIR AuditEvent-leaning)."""

    LOGIN = "login"
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    FINALIZE = "finalize"
    DOWNLOAD = "download"


class AuditEntity(StrEnum):
    """The kind of record an audit event concerns."""

    SESSION = "session"
    PATIENT = "patient"
    STUDY = "study"
    REPORT = "report"
