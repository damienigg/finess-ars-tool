"""Routes pour la gestion des dossiers (workflow)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Dossier, EvenementDossier, Etablissement,
    TypeDemande, StatutDemande,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])
templates = Jinja2Templates(directory="app/templates")


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

    # Stats kanban
    kanban = dict(
        db.query(Dossier.statut, func.count(Dossier.id))
        .group_by(Dossier.statut)
        .all()
    )

    return templates.TemplateResponse(
        "workflow/liste.html",
        {
            "request": request,
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
async def formulaire_nouveau(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "workflow/nouveau.html",
        {
            "request": request,
            "types": [t.value for t in TypeDemande],
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
            pass

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

    return RedirectResponse(url=f"/workflow/{dossier.id}", status_code=303)


@router.get("/{dossier_id}", response_class=HTMLResponse)
async def detail_dossier(request: Request, dossier_id: int, db: Session = Depends(get_db)):
    dossier = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not dossier:
        return templates.TemplateResponse(
            "workflow/detail.html",
            {"request": request, "dossier": None},
        )

    etab = None
    if dossier.nofinesset:
        etab = db.query(Etablissement).filter(
            Etablissement.nofinesset == dossier.nofinesset
        ).first()

    return templates.TemplateResponse(
        "workflow/detail.html",
        {
            "request": request,
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
    dossier.updated_at = datetime.utcnow()

    if nouveau_statut in (StatutDemande.VALIDE.value, StatutDemande.REJETE.value, StatutDemande.TRANSMIS_DREES.value):
        dossier.date_cloture = datetime.utcnow()

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
    dossier.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/workflow/{dossier_id}", status_code=303)
