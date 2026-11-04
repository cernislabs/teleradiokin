"""FastAPI application factory and middleware wiring."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.errors import ServiceError

from app.api.routers import (
    audit,
    auth,
    encounters,
    health,
    patients,
    reports,
    studies,
    users,
)
from app.core.config import get_settings, validate_security
from app.core.dependencies import get_storage
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.seed import seed_initial_data
from app.services.maintenance import purge_stale_uploads, recover_stale_processing


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: refuse to boot with insecure config outside development, seed
    # initial accounts (idempotent), recover studies left mid-processing by a
    # previous crash/restart, and garbage-collect abandoned uploads. Schema is
    # managed by Alembic migrations (run by the entrypoint), not created here.
    validate_security(get_settings())
    await seed_initial_data()
    await recover_stale_processing(AsyncSessionLocal)
    await purge_stale_uploads(AsyncSessionLocal, get_storage())
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Teleradiokin API",
        version="0.1.0",
        description="Teleradiology MVP backend (FastAPI).",
        docs_url="/swagger" if settings.swagger_enabled else None,
        openapi_url="/openapi.json" if settings.swagger_enabled else None,
        lifespan=lifespan,
    )

    # Session factory used by background tasks (overridable in tests).
    app.state.session_factory = AsyncSessionLocal

    @app.exception_handler(ServiceError)
    async def _service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Auth is Bearer-token (localStorage), not cookies, so credentialed CORS
        # is unnecessary and only widens exposure.
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers (feature routers registered as iterations land).
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(patients.router)
    app.include_router(encounters.router)
    app.include_router(studies.router)
    app.include_router(reports.router)
    app.include_router(audit.router)

    return app


app = create_app()
