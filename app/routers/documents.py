"""Routes pour la génération de documents."""

from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.documents import lister_modeles, generer_document

router = APIRouter(prefix="/documents", tags=["documents"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def page_documents(request: Request):
    modeles = lister_modeles()
    return templates.TemplateResponse(
        "documents/liste.html",
        {"request": request, "modeles": modeles},
    )


@router.get("/generer", response_class=HTMLResponse)
async def formulaire_generer(
    request: Request,
    modele_id: str = Query(...),
):
    from app.services.documents import get_modele
    modele = get_modele(modele_id)
    return templates.TemplateResponse(
        "documents/generer.html",
        {"request": request, "modele": modele},
    )


@router.post("/generer", response_class=HTMLResponse)
async def generer(
    request: Request,
    modele_id: str = Form(...),
    nofinesset: str = Form(...),
    ars_nom: str = Form("[Nom de l'ARS]"),
    ars_adresse: str = Form("[Adresse de l'ARS]"),
    lieu: str = Form("[Ville]"),
    signataire_nom: str = Form("[Nom du signataire]"),
    signataire_titre: str = Form("[Titre du signataire]"),
    delai_jours: str = Form("30"),
    db: Session = Depends(get_db),
):
    variables_extra = {
        "ars_nom": ars_nom,
        "ars_adresse": ars_adresse,
        "lieu": lieu,
        "signataire_nom": signataire_nom,
        "signataire_titre": signataire_titre,
        "delai_jours": delai_jours,
    }
    texte = generer_document(db, modele_id, nofinesset, variables_extra)

    from app.services.documents import get_modele
    modele = get_modele(modele_id)

    return templates.TemplateResponse(
        "documents/resultat.html",
        {"request": request, "texte": texte, "modele": modele, "nofinesset": nofinesset},
    )


@router.post("/telecharger")
async def telecharger_texte(texte: str = Form(...)):
    return PlainTextResponse(
        content=texte,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=courrier_finess.txt"},
    )
