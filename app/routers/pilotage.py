"""Routes pour le tableau de bord de pilotage."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.pilotage import (
    calculer_indicateurs_globaux,
    repartition_par_categorie,
    repartition_par_departement,
    dossiers_par_statut,
    dossiers_en_retard,
    comparaison_inter_departementale,
)

router = APIRouter(prefix="/pilotage", tags=["pilotage"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def tableau_pilotage(request: Request, db: Session = Depends(get_db)):
    indicateurs = calculer_indicateurs_globaux(db)
    par_categorie = repartition_par_categorie(db)
    par_departement = repartition_par_departement(db)
    par_statut = dossiers_par_statut(db)
    retards = dossiers_en_retard(db)
    inter_dept = comparaison_inter_departementale(db)

    return templates.TemplateResponse(
        "pilotage.html",
        {
            "request": request,
            "indicateurs": indicateurs,
            "par_categorie": par_categorie,
            "par_departement": par_departement,
            "par_statut": par_statut,
            "retards": retards,
            "inter_dept": inter_dept,
        },
    )
