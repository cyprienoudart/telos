"""FastAPI application — wires routes, CORS, and service singletons."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is importable (for ali/ and agent/ packages)
_project_root = Path(__file__).resolve().parent.parent.parent
for pkg_dir in [str(_project_root), str(_project_root / "agent")]:
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

from server.routes import build, conversation
from server.services.build_runner import BuildRunner
from server.services.session import SessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    missions_path = os.environ.get(
        "MISSIONS_PATH",
        str(_project_root / "train" / "data" / "missions.jsonl"),
    )
    session_store = SessionStore(missions_path=missions_path)
    build_runner = BuildRunner()

    # Inject singletons into route modules
    conversation.store = session_store
    build.store = session_store
    build.runner = build_runner

    yield

    # ── Shutdown ──
    conversation.store = None
    build.store = None
    build.runner = None


app = FastAPI(
    title="Telos Server",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversation.router)
app.include_router(build.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def cli():
    """Entry point for `telos-server` command."""
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    cli()
