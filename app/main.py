"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.logging_conf import configure_logging
from app.paths import STATIC_DIR
from app.routers import (
    cartographie,
    documents,
    etablissements,
    pilotage,
    qualite,
    reconciliation,
    workflow,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger = logging.getLogger("app.startup")
    logger.info(
        "Starting Finess-for-Laure (env=%s, db=%s)",
        settings.environment,
        settings.database_url.split("://", 1)[0],
    )
    init_db()
    yield
    logger.info("Shutting down Finess-for-Laure")


app = FastAPI(
    title="Finess-for-Laure",
    description="Outil d'assistance à la gestion du répertoire FINESS",
    version="0.3.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(etablissements.router)
app.include_router(qualite.router)
app.include_router(workflow.router)
app.include_router(reconciliation.router)
app.include_router(cartographie.router)
app.include_router(documents.router)
app.include_router(pilotage.router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    """Health probe pour orchestrateur / reverse proxy."""
    return {"status": "ok", "version": app.version}
