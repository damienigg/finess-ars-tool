"""Routes pour la génération de documents."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.documents import generer_document, get_modele, lister_modeles

logger = logging.getLogger(__name__)

from app.paths import templates


router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_class=HTMLResponse)
async def page_documents(request: Request):
    return templates.TemplateResponse(
        request,
        "documents/liste.html",
        {"modeles": lister_modeles()},
    )


@router.get("/generer", response_class=HTMLResponse)
async def formulaire_generer(
    request: Request,
    modele_id: str = Query(...),
    nofinesset: str = Query(""),
):
    modele = get_modele(modele_id)
    return templates.TemplateResponse(
        request,
        "documents/generer.html",
        {"modele": modele, "nofinesset": nofinesset},
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
    modele = get_modele(modele_id)
    logger.info("Document %s généré pour %s", modele_id, nofinesset)

    return templates.TemplateResponse(
        request,
        "documents/resultat.html",
        {"texte": texte, "modele": modele, "nofinesset": nofinesset},
    )


@router.post("/telecharger")
async def telecharger_texte(texte: str = Form(...)):
    return PlainTextResponse(
        content=texte,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=courrier_finess.txt"},
    )
