"""Routes pour le tableau de bord de pilotage."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.pilotage import (
    calculer_indicateurs_globaux,
    comparaison_inter_departementale,
    dossiers_en_retard,
    dossiers_par_statut,
    repartition_par_categorie,
    repartition_par_departement,
)

from app.paths import templates


router = APIRouter(prefix="/pilotage", tags=["pilotage"])


@router.get("", response_class=HTMLResponse)
async def tableau_pilotage(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "pilotage.html",
        {
            "indicateurs": calculer_indicateurs_globaux(db),
            "par_categorie": repartition_par_categorie(db),
            "par_departement": repartition_par_departement(db),
            "par_statut": dossiers_par_statut(db),
            "retards": dossiers_en_retard(db),
            "inter_dept": comparaison_inter_departementale(db),
        },
    )


def _csv_stream(
    filename: str, header: list[str], rows: list[list]
) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export")
async def exporter_pilotage(
    quoi: str = Query("categories", pattern="^(categories|departements|inter_dept|retards)$"),
    db: Session = Depends(get_db),
):
    if quoi == "categories":
        data = repartition_par_categorie(db)
        return _csv_stream(
            "pilotage_categories.csv",
            ["code", "libelle", "count"],
            [[d["code"] or "", d["libelle"], d["count"]] for d in data],
        )
    if quoi == "departements":
        data = repartition_par_departement(db)
        return _csv_stream(
            "pilotage_departements.csv",
            ["code", "libelle", "count"],
            [[d["code"] or "", d["libelle"], d["count"]] for d in data],
        )
    if quoi == "inter_dept":
        data = comparaison_inter_departementale(db)
        return _csv_stream(
            "pilotage_inter_departemental.csv",
            ["departement", "nb_et", "nb_anomalies", "taux_anomalies"],
            [
                [d["departement"] or "", d["nb_et"], d["nb_anomalies"], d["taux_anomalies"]]
                for d in data
            ],
        )
    # retards
    data = dossiers_en_retard(db)
    return _csv_stream(
        "pilotage_retards.csv",
        ["id", "nofinesset", "type_demande", "statut", "date_echeance", "agent_instructeur"],
        [
            [
                d.id,
                d.nofinesset or "",
                d.type_demande,
                d.statut,
                d.date_echeance.isoformat() if d.date_echeance else "",
                d.agent_instructeur or "",
            ]
            for d in data
        ],
    )
