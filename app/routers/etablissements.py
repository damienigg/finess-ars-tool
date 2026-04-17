import io
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Etablissement, EntiteJuridique

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

REGIONS = {
    "01": "Guadeloupe",
    "02": "Martinique",
    "03": "Guyane",
    "04": "La Réunion",
    "06": "Mayotte",
    "11": "Île-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur",
    "94": "Corse",
}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    total_et = db.query(func.count(Etablissement.nofinesset)).scalar()
    total_ej = db.query(func.count(EntiteJuridique.nofinesset)).scalar()

    par_region = (
        db.query(Etablissement.libregion, func.count(Etablissement.nofinesset))
        .group_by(Etablissement.libregion)
        .order_by(func.count(Etablissement.nofinesset).desc())
        .limit(10)
        .all()
    )

    par_categorie = (
        db.query(Etablissement.libcategetab, func.count(Etablissement.nofinesset))
        .group_by(Etablissement.libcategetab)
        .order_by(func.count(Etablissement.nofinesset).desc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "total_et": total_et,
            "total_ej": total_ej,
            "par_region": par_region,
            "par_categorie": par_categorie,
        },
    )


@router.get("/recherche", response_class=HTMLResponse)
async def recherche(
    request: Request,
    q: Optional[str] = Query(None, description="Recherche libre"),
    region: Optional[str] = Query(None),
    departement: Optional[str] = Query(None),
    categorie: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    per_page = 25
    query = db.query(Etablissement)

    if q:
        like_q = f"%{q}%"
        query = query.filter(
            or_(
                Etablissement.nofinesset.ilike(like_q),
                Etablissement.rs.ilike(like_q),
                Etablissement.rslongue.ilike(like_q),
                Etablissement.libcommune.ilike(like_q),
                Etablissement.codepostal.ilike(like_q),
            )
        )
    if region:
        query = query.filter(Etablissement.region == region)
    if departement:
        query = query.filter(Etablissement.departement == departement)
    if categorie:
        query = query.filter(Etablissement.categetab == categorie)

    total = query.count()
    resultats = (
        query.order_by(Etablissement.rs).offset((page - 1) * per_page).limit(per_page).all()
    )
    total_pages = max(1, (total + per_page - 1) // per_page)

    categories = (
        db.query(Etablissement.categetab, Etablissement.libcategetab)
        .distinct()
        .order_by(Etablissement.libcategetab)
        .all()
    )

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "resultats": resultats,
            "q": q or "",
            "region": region or "",
            "departement": departement or "",
            "categorie": categorie or "",
            "regions": REGIONS,
            "categories": categories,
            "total": total,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.get("/etablissement/{nofinesset}", response_class=HTMLResponse)
async def detail_etablissement(
    request: Request, nofinesset: str, db: Session = Depends(get_db)
):
    etab = db.query(Etablissement).filter(Etablissement.nofinesset == nofinesset).first()
    ej = None
    autres_et = []
    if etab and etab.nofinessej:
        ej = (
            db.query(EntiteJuridique)
            .filter(EntiteJuridique.nofinesset == etab.nofinessej)
            .first()
        )
        autres_et = (
            db.query(Etablissement)
            .filter(
                Etablissement.nofinessej == etab.nofinessej,
                Etablissement.nofinesset != nofinesset,
            )
            .all()
        )

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "etab": etab,
            "ej": ej,
            "autres_et": autres_et,
        },
    )


@router.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return templates.TemplateResponse("import.html", {"request": request})


@router.post("/import", response_class=HTMLResponse)
async def import_data(
    request: Request,
    fichier_et: UploadFile = File(..., description="Fichier CSV des établissements"),
    fichier_ej: Optional[UploadFile] = File(None, description="Fichier CSV des entités juridiques"),
    db: Session = Depends(get_db),
):
    messages = []

    try:
        # Import entités juridiques
        if fichier_ej and fichier_ej.filename:
            content = await fichier_ej.read()
            df_ej = pd.read_csv(
                io.BytesIO(content), sep=";", dtype=str, encoding="utf-8"
            )
            df_ej.columns = [c.strip().lower() for c in df_ej.columns]
            count = 0
            for _, row in df_ej.iterrows():
                data = {c: row.get(c) for c in EntiteJuridique.__table__.columns.keys() if c in row.index}
                if "nofinesset" in data and data["nofinesset"]:
                    db.merge(EntiteJuridique(**data))
                    count += 1
            db.commit()
            messages.append(f"{count} entités juridiques importées.")

        # Import établissements
        content = await fichier_et.read()
        df_et = pd.read_csv(
            io.BytesIO(content), sep=";", dtype=str, encoding="utf-8"
        )
        df_et.columns = [c.strip().lower() for c in df_et.columns]
        count = 0
        for _, row in df_et.iterrows():
            data = {c: row.get(c) for c in Etablissement.__table__.columns.keys() if c in row.index}
            if "nofinesset" in data and data["nofinesset"]:
                db.merge(Etablissement(**data))
                count += 1
        db.commit()
        messages.append(f"{count} établissements importés.")

    except Exception as e:
        messages.append(f"Erreur lors de l'import : {e}")

    return templates.TemplateResponse(
        "import.html", {"request": request, "messages": messages}
    )
