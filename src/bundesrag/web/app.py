import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from bundesrag.config import Settings
from bundesrag.i18n import set_language
from bundesrag.logging_config import LOGGER_NAME, setup_logging
from bundesrag.web import routes_jobs, routes_sync
from bundesrag.web.jobs import JobManager

logger = logging.getLogger(LOGGER_NAME)


def _frontend_dist_path() -> Path:
    env_path = os.environ.get("BUNDESRAG_FRONTEND_DIST")
    if env_path:
        return Path(env_path)
    # Resolves to <repo root>/frontend/dist when running from the source tree;
    # installed packages (e.g. in Docker) must set BUNDESRAG_FRONTEND_DIST.
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()
    set_language(settings.language)
    setup_logging(settings)

    app = FastAPI(title="Bundes-RAG")
    app.state.settings = settings
    app.state.job_manager = JobManager()
    app.include_router(routes_jobs.router, prefix="/api")
    app.include_router(routes_sync.router, prefix="/api")

    frontend_dist = _frontend_dist_path()
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        logger.warning("frontend build not found at %s, serving API only", frontend_dist)

    return app
