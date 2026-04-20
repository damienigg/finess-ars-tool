"""Routes pour la gestion des dossiers (workflow)."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Dossier,
    Etablissement,
    EvenementDossier,
    StatutDemande,
    TypeDemande,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)

from app.paths import templates


router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.get("", response_class=HTMLResponse)
async def liste_dossiers(
    request: Request,
    statut: Optional[str] = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    per_page = 25
    query = db.query(Dossier)
    if statut:
        query = query.filter(Dossier.statut == statut)
    total = query.count()
    dossiers = (
        query.order_by(Dossier.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    kanban = dict(
        db.query(Dossier.statut, func.count(Dossier.id))
        .group_by(Dossier.statut)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "workflow/liste.html",
        {
            "dossiers": dossiers,
            "statut_filtre": statut or "",
            "statuts": [s.value for s in StatutDemande],
            "types": [t.value for t in TypeDemande],
            "kanban": kanban,
            "total": total,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.get("/nouveau", response_class=HTMLResponse)
async def formulaire_nouveau(
    request: Request,
    nofinesset: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    etab = None
    if nofinesset:
        etab = (
            db.query(Etablissement)
            .filter(Etablissement.nofinesset == nofinesset)
            .first()
        )
    return templates.TemplateResponse(
        request,
        "workflow/nouveau.html",
        {
            "types": [t.value for t in TypeDemande],
            "nofinesset": nofinesset or "",
            "etab": etab,
        },
    )


@router.post("/nouveau")
async def creer_dossier(
    request: Request,
    nofinesset: str = Form(...),
    type_demande: str = Form(...),
    objet: str = Form(""),
    demandeur: str = Form(""),
    agent_instructeur: str = Form(""),
    date_echeance: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    echeance = None
    if date_echeance:
        try:
            echeance = datetime.strptime(date_echeance, "%Y-%m-%d")
        except ValueError:
            logger.warning("Date d'échéance invalide : %r", date_echeance)

    dossier = Dossier(
        nofinesset=nofinesset,
        type_demande=type_demande,
        statut=StatutDemande.RECU.value,
        objet=objet,
        demandeur=demandeur,
        agent_instructeur=agent_instructeur,
        date_echeance=echeance,
    )
    db.add(dossier)
    db.flush()

    evt = EvenementDossier(
        dossier_id=dossier.id,
        auteur=agent_instructeur or "Système",
        type_evenement="changement_statut",
        nouveau_statut=StatutDemande.RECU.value,
        commentaire="Dossier créé",
    )
    db.add(evt)
    db.commit()
    logger.info("Dossier %d créé pour ET %s", dossier.id, nofinesset)

    return RedirectResponse(url=f"/workflow/{dossier.id}", status_code=303)


@router.get("/export")
async def exporter_dossiers(
    statut: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Dossier)
    if statut:
        query = query.filter(Dossier.statut == statut)
    dossiers = query.order_by(Dossier.updated_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "id", "nofinesset", "type_demande", "statut", "objet",
        "demandeur", "agent_instructeur",
        "date_reception", "date_echeance", "date_cloture",
        "created_at", "updated_at",
    ])
    for d in dossiers:
        writer.writerow([
            d.id, d.nofinesset or "", d.type_demande, d.statut, d.objet or "",
            d.demandeur or "", d.agent_instructeur or "",
            d.date_reception.isoformat() if d.date_reception else "",
            d.date_echeance.isoformat() if d.date_echeance else "",
            d.date_cloture.isoformat() if d.date_cloture else "",
            d.created_at.isoformat() if d.created_at else "",
            d.updated_at.isoformat() if d.updated_at else "",
        ])
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dossiers_finess.csv"},
    )


@router.get("/{dossier_id}", response_class=HTMLResponse)
async def detail_dossier(
    request: Request, dossier_id: int, db: Session = Depends(get_db)
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        return templates.TemplateResponse(
            request,
            "workflow/detail.html",
            {"dossier": None},
        )

    etab = None
    if dossier.nofinesset:
        etab = (
            db.query(Etablissement)
            .filter(Etablissement.nofinesset == dossier.nofinesset)
            .first()
        )

    return templates.TemplateResponse(
        request,
        "workflow/detail.html",
        {
            "dossier": dossier,
            "etab": etab,
            "statuts": [s.value for s in StatutDemande],
        },
    )


@router.post("/{dossier_id}/statut")
async def changer_statut(
    dossier_id: int,
    nouveau_statut: str = Form(...),
    commentaire: str = Form(""),
    auteur: str = Form(""),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        return RedirectResponse(url="/workflow", status_code=303)

    ancien = dossier.statut
    dossier.statut = nouveau_statut
    dossier.updated_at = utcnow()

    if nouveau_statut in (
        StatutDemande.VALIDE.value,
        StatutDemande.REJETE.value,
        StatutDemande.TRANSMIS_DREES.value,
    ):
        dossier.date_cloture = utcnow()

    evt = EvenementDossier(
        dossier_id=dossier.id,
        auteur=auteur or "Agent",
        type_evenement="changement_statut",
        ancien_statut=ancien,
        nouveau_statut=nouveau_statut,
        commentaire=commentaire,
    )
    db.add(evt)
    db.commit()
    logger.info("Dossier %d : %s -> %s", dossier.id, ancien, nouveau_statut)

    return RedirectResponse(url=f"/workflow/{dossier_id}", status_code=303)


@router.post("/{dossier_id}/commentaire")
async def ajouter_commentaire(
    dossier_id: int,
    commentaire: str = Form(...),
    auteur: str = Form(""),
    db: Session = Depends(get_db),
):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        return RedirectResponse(url="/workflow", status_code=303)

    evt = EvenementDossier(
        dossier_id=dossier.id,
        auteur=auteur or "Agent",
        type_evenement="commentaire",
        commentaire=commentaire,
    )
    db.add(evt)
    dossier.updated_at = utcnow()
    db.commit()

    return RedirectResponse(url=f"/workflow/{dossier_id}", status_code=303)
