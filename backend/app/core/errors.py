"""Shared application error type.

Services raise :class:`ServiceError` to signal an HTTP-meaningful failure
(not found, conflict, validation) without importing FastAPI. A single exception
handler (registered in ``app.main``) turns it into the HTTP response, so routers
delegate to services directly and no longer wrap every call in try/except.
"""


class ServiceError(Exception):
    """An expected, HTTP-mappable failure from the service layer."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
