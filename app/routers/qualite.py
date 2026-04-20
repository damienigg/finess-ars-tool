"""Routes pour le contrôle qualité et la détection d'anomalies."""

from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Anomalie
from app.services.qualite import executer_controle_qualite, score_qualite

logger = logging.getLogger(__name__)

from app.paths import templates


router = APIRouter(prefix="/qualite", tags=["qualite"])


def _current_anomalies(db: Session, limit: int = 200):
    return (
        db.query(Anomalie)
        .filter(Anomalie.resolved == False)  # noqa: E712
        .order_by(Anomalie.niveau, Anomalie.regle)
        .limit(limit)
        .all()
    )


@router.get("", response_class=HTMLResponse)
async def tableau_qualite(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "qualite.html",
        {
            "scores": score_qualite(db),
            "anomalies": _current_anomalies(db),
        },
    )


@router.post("/executer", response_class=HTMLResponse)
async def lancer_controle(request: Request, db: Session = Depends(get_db)):
    nouvelles = executer_controle_qualite(db)
    logger.info("Contrôle qualité : %d anomalie(s) détectée(s)", len(nouvelles))
    return templates.TemplateResponse(
        request,
        "qualite.html",
        {
            "scores": score_qualite(db),
            "anomalies": _current_anomalies(db),
            "message": f"Contrôle terminé : {len(nouvelles)} anomalie(s) détectée(s).",
        },
    )


@router.post("/resoudre/{anomalie_id}")
async def resoudre_anomalie(anomalie_id: int, db: Session = Depends(get_db)):
    anom = db.query(Anomalie).filter(Anomalie.id == anomalie_id).first()
    if anom:
        anom.resolved = True
        db.commit()
    return RedirectResponse(url="/qualite", status_code=303)


@router.get("/export")
async def exporter_anomalies(db: Session = Depends(get_db)):
    anomalies = (
        db.query(Anomalie)
        .filter(Anomalie.resolved == False)  # noqa: E712
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        ["nofinesset", "nofinessej", "regle", "niveau", "message", "detail", "date_detection"]
    )
    for a in anomalies:
        writer.writerow([
            a.nofinesset or "", a.nofinessej or "", a.regle, a.niveau,
            a.message, a.detail or "", str(a.date_detection or ""),
        ])
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=anomalies_finess.csv"},
    )
