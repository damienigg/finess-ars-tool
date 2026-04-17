"""Routes pour la réconciliation avec les sources externes."""

from typing import Optional

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.reconciliation import diff_extractions, comparer_avec_sae

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def page_reconciliation(request: Request):
    return templates.TemplateResponse("reconciliation.html", {"request": request})


@router.post("/diff", response_class=HTMLResponse)
async def diff_fichiers(
    request: Request,
    fichier_ancien: UploadFile = File(...),
    fichier_nouveau: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ancien = await fichier_ancien.read()
    nouveau = await fichier_nouveau.read()
    try:
        result = diff_extractions(ancien, nouveau)
        return templates.TemplateResponse(
            "reconciliation.html",
            {
                "request": request,
                "diff": result,
                "action": "diff",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "reconciliation.html",
            {"request": request, "erreur": str(e)},
        )


@router.post("/sae", response_class=HTMLResponse)
async def comparer_sae(
    request: Request,
    fichier_sae: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    contenu = await fichier_sae.read()
    try:
        result = comparer_avec_sae(db, contenu)
        return templates.TemplateResponse(
            "reconciliation.html",
            {
                "request": request,
                "sae": result,
                "action": "sae",
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "reconciliation.html",
            {"request": request, "erreur": str(e)},
        )
