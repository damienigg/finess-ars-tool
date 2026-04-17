from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import (
    etablissements,
    qualite,
    workflow,
    reconciliation,
    cartographie,
    documents,
    pilotage,
)

app = FastAPI(
    title="FINESS ARS - Outil d'assistance",
    description="Outil web d'aide à la gestion du répertoire FINESS pour les ARS",
    version="0.2.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(etablissements.router)
app.include_router(qualite.router)
app.include_router(workflow.router)
app.include_router(reconciliation.router)
app.include_router(cartographie.router)
app.include_router(documents.router)
app.include_router(pilotage.router)


@app.on_event("startup")
def on_startup():
    init_db()
