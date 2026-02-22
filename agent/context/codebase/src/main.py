"""
main.py — Application entry point for Project Telos.

Starts a FastAPI server with:
  - Authentication middleware (JWT + refresh-token rotation)
  - Rate limiting (Redis-backed)
  - Database connection pool (asyncpg)
  - Prometheus metrics endpoint
"""

from __future__ import annotations

import os
import logging

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from auth.handler import AuthHandler, auth_middleware
from models.user import UserModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Telos API",
        version="2.3.1",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # CORS — tighten in production via ALLOWED_ORIGINS env var
    origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(auth_middleware)

    # Prometheus
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Register routers
    from routers import users, workflows, health  # local imports to avoid circular
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(users.router, prefix="/api/v2/users", tags=["users"])
    app.include_router(workflows.router, prefix="/api/v2/workflows", tags=["workflows"])

    return app


# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------

app = create_app()


@app.on_event("startup")
async def startup() -> None:
    db_url = os.environ["DATABASE_URL"]
    app.state.db_pool = await asyncpg.create_pool(
        db_url,
        min_size=5,
        max_size=int(os.environ.get("DB_POOL_MAX", "50")),  # INFRA-89 fix
        command_timeout=30,
    )
    app.state.auth = AuthHandler(
        secret_key=os.environ["SECRET_KEY"],
        redis_url=os.environ["REDIS_URL"],
    )
    logger.info("Startup complete — pool max_size=%s", app.state.db_pool.get_size())


@app.on_event("shutdown")
async def shutdown() -> None:
    await app.state.db_pool.close()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
