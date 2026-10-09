"""Main FastAPI application entry point for aria-local-agent."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat_ws, health, sessions
from app.config import get_settings
from app.db.connection import get_database
from app.db.schema import init_db
from app.llm.persona import load_persona

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aria.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    settings = get_settings()
    logger.info(f"Starting aria-local-agent daemon (data_dir: {settings.data_dir_path})")

    # 1. Initialize SQLite schema & WAL mode
    db = get_database()
    async with db.get_connection() as conn:
        await init_db(conn)
    logger.info("SQLite database schema initialized in WAL mode")

    # 2. Ensure persona.md exists
    load_persona()
    logger.info(f"Loaded persona prompt from {settings.persona_path}")

    yield

    logger.info("Shutting down aria-local-agent daemon")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="aria-local-agent",
        description="Fully private, local-first personal AI assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS for local development and Tailscale clients
    origins = settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(chat_ws.router)

    # Mount frontend static build if present
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="static")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    cfg = get_settings()
    uvicorn.run(
        "app.main:app",
        host=cfg.host,
        port=cfg.port,
        reload=cfg.aria_env == "development",
    )
