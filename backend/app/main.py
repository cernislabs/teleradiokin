"""FastAPI application factory and middleware wiring."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    auth,
    encounters,
    health,
    patients,
    reports,
    studies,
    users,
)
from app.core.config import get_settings
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.seed import seed_initial_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: seed initial accounts (idempotent). Schema itself is managed by
    # Alembic migrations (run by the container entrypoint), not created here.
    await seed_initial_data()
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
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

    return app


app = create_app()
