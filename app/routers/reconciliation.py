"""Routes pour la réconciliation avec les sources externes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.reconciliation import (
    comparer_avec_sae,
    diff_extractions,
    verifier_siret_sirene,
)

logger = logging.getLogger(__name__)

from app.paths import templates


router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.get("", response_class=HTMLResponse)
async def page_reconciliation(request: Request):
    return templates.TemplateResponse(request, "reconciliation.html", {})


@router.post("/diff", response_class=HTMLResponse)
async def diff_fichiers(
    request: Request,
    fichier_ancien: UploadFile = File(...),
    fichier_nouveau: UploadFile = File(...),
):
    ancien = await fichier_ancien.read()
    nouveau = await fichier_nouveau.read()
    try:
        result = diff_extractions(ancien, nouveau)
        return templates.TemplateResponse(
            request,
            "reconciliation.html",
            {"diff": result, "action": "diff"},
        )
    except ValueError as exc:
        logger.warning("Diff CSV invalide : %s", exc)
        return templates.TemplateResponse(
            request, "reconciliation.html", {"erreur": str(exc)}
        )
    except UnicodeDecodeError:
        return templates.TemplateResponse(
            request, "reconciliation.html",
            {"erreur": "Encodage invalide (UTF-8 attendu)."},
        )
    except Exception as exc:  # noqa: BLE001 - last-resort guard
        logger.exception("Diff : erreur inattendue")
        return templates.TemplateResponse(
            request, "reconciliation.html", {"erreur": f"Erreur de lecture : {exc}"}
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
            request,
            "reconciliation.html",
            {"sae": result, "action": "sae"},
        )
    except ValueError as exc:
        logger.warning("SAE CSV invalide : %s", exc)
        return templates.TemplateResponse(
            request, "reconciliation.html", {"erreur": str(exc)}
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("SAE : erreur inattendue")
        return templates.TemplateResponse(
            request, "reconciliation.html", {"erreur": f"Erreur : {exc}"}
        )


@router.get("/sirene", response_class=HTMLResponse)
async def sirene_form(
    request: Request,
    siret: Optional[str] = None,
):
    return templates.TemplateResponse(
        request, "sirene.html", {"siret": siret or "", "result": None}
    )


@router.post("/sirene", response_class=HTMLResponse)
async def sirene_lookup(request: Request, siret: str = Form(...)):
    result = await verifier_siret_sirene(siret.strip())
    logger.info(
        "SIRENE lookup %s : existe=%s actif=%s erreur=%s",
        siret, result.get("existe"), result.get("actif"), result.get("erreur"),
    )
    return templates.TemplateResponse(
        request, "sirene.html", {"siret": siret, "result": result}
    )
