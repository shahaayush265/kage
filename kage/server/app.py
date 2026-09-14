"""FastAPI application factory for the Kage Host Bridge API and Web Console."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from kage.server.routes.agent import router as agent_router
from kage.server.routes.gui import router as gui_router
from kage.server.routes.instances import router as instances_router
from kage.server.routes.shell import router as shell_router
from kage.server.routes.vnc import router as vnc_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(target_instance: Optional[str] = None) -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Kage Host Bridge API",
        description="Standardized REST & WebSocket interface for VM agent orchestration",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(instances_router, prefix="/api/v1")
    app.include_router(shell_router, prefix="/api/v1")
    app.include_router(gui_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    app.include_router(vnc_router)

    # Mount static files
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index_root():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse("<h1>Kage Web Console</h1><p>Static console not built yet.</p>")

    @app.get("/view/{name}", response_class=HTMLResponse)
    async def view_instance(name: str):
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(f"<h1>Kage Instance: {name}</h1>")

    return app
