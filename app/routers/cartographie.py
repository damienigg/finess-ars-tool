"""Routes pour la cartographie interactive."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Etablissement
from app.services.cartographie import (
    detecter_coordonnees_aberrantes,
    get_etablissements_geolocalises,
    zones_blanches,
)

from app.paths import templates


router = APIRouter(prefix="/cartographie", tags=["cartographie"])


@router.get("", response_class=HTMLResponse)
async def page_carte(request: Request):
    return templates.TemplateResponse(request, "cartographie.html", {})


@router.get("/api/points")
async def api_points(
    region: Optional[str] = None,
    departement: Optional[str] = None,
    categetab: Optional[str] = None,
    db: Session = Depends(get_db),
):
    filtres = {}
    if region:
        filtres["region"] = region
    if departement:
        filtres["departement"] = departement
    if categetab:
        filtres["categetab"] = categetab

    points = get_etablissements_geolocalises(db, **filtres)
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
                "properties": {
                    "nofinesset": p.nofinesset,
                    "rs": p.rs,
                    "categetab": p.categetab,
                    "libcategetab": p.libcategetab,
                    "commune": p.commune,
                    "departement": p.departement,
                },
            }
            for p in points
        ],
    }
    return JSONResponse(content=geojson)


@router.get("/api/anomalies-geo")
async def api_anomalies_geo(db: Session = Depends(get_db)):
    return JSONResponse(content=detecter_coordonnees_aberrantes(db))


@router.get("/anomalies", response_class=HTMLResponse)
async def page_anomalies_geo(request: Request, db: Session = Depends(get_db)):
    anomalies = detecter_coordonnees_aberrantes(db)
    return templates.TemplateResponse(
        request,
        "cartographie_anomalies.html",
        {"anomalies": anomalies},
    )


@router.get("/zones-blanches", response_class=HTMLResponse)
async def page_zones_blanches(
    request: Request,
    categetab: Optional[str] = Query(None),
    rayon_km: float = Query(30.0, gt=0, le=500),
    db: Session = Depends(get_db),
):
    # Liste déroulante : catégories disponibles.
    categories = (
        db.query(Etablissement.categetab, Etablissement.libcategetab)
        .filter(Etablissement.categetab.isnot(None), Etablissement.categetab != "")
        .distinct()
        .order_by(Etablissement.libcategetab)
        .all()
    )
    isoles = []
    if categetab:
        isoles = zones_blanches(db, categetab=categetab, rayon_km=rayon_km)

    return templates.TemplateResponse(
        request,
        "cartographie_zones.html",
        {
            "categories": categories,
            "categetab": categetab or "",
            "rayon_km": rayon_km,
            "isoles": isoles,
        },
    )
