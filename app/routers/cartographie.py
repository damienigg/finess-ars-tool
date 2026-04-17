"""Routes pour la cartographie interactive."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.cartographie import (
    get_etablissements_geolocalises,
    detecter_coordonnees_aberrantes,
)

router = APIRouter(prefix="/cartographie", tags=["cartographie"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def page_carte(request: Request):
    return templates.TemplateResponse("cartographie.html", {"request": request})


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
    anomalies = detecter_coordonnees_aberrantes(db)
    return JSONResponse(content=anomalies)
