from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import etablissements

app = FastAPI(
    title="FINESS ARS - Outil d'assistance",
    description="Outil web d'aide à la gestion du répertoire FINESS pour les ARS",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(etablissements.router)


@app.on_event("startup")
def on_startup():
    init_db()
