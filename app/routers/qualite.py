"""Routes pour le contrôle qualité et la détection d'anomalies."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import csv
import io

from app.database import get_db
from app.models import Anomalie
from app.services.qualite import executer_controle_qualite, score_qualite

router = APIRouter(prefix="/qualite", tags=["qualite"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def tableau_qualite(request: Request, db: Session = Depends(get_db)):
    scores = score_qualite(db)
    anomalies = (
        db.query(Anomalie)
        .filter(Anomalie.resolved == False)
        .order_by(Anomalie.niveau, Anomalie.regle)
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "qualite.html",
        {"request": request, "scores": scores, "anomalies": anomalies},
    )


@router.post("/executer", response_class=HTMLResponse)
async def lancer_controle(request: Request, db: Session = Depends(get_db)):
    nouvelles = executer_controle_qualite(db)
    scores = score_qualite(db)
    anomalies = (
        db.query(Anomalie)
        .filter(Anomalie.resolved == False)
        .order_by(Anomalie.niveau, Anomalie.regle)
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "qualite.html",
        {
            "request": request,
            "scores": scores,
            "anomalies": anomalies,
            "message": f"Contrôle terminé : {len(nouvelles)} anomalie(s) détectée(s).",
        },
    )


@router.post("/resoudre/{anomalie_id}")
async def resoudre_anomalie(anomalie_id: int, db: Session = Depends(get_db)):
    anom = db.query(Anomalie).filter(Anomalie.id == anomalie_id).first()
    if anom:
        anom.resolved = True
        db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/qualite", status_code=303)


@router.get("/export")
async def exporter_anomalies(db: Session = Depends(get_db)):
    anomalies = db.query(Anomalie).filter(Anomalie.resolved == False).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["nofinesset", "nofinessej", "regle", "niveau", "message", "detail", "date_detection"])
    for a in anomalies:
        writer.writerow([
            a.nofinesset or "", a.nofinessej or "", a.regle, a.niveau,
            a.message, a.detail or "", str(a.date_detection or ""),
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=anomalies_finess.csv"},
    )
