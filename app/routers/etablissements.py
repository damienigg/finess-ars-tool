"""Routes pour la consultation et l'import des établissements FINESS."""

from __future__ import annotations

import io
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EntiteJuridique, Etablissement

logger = logging.getLogger(__name__)

from app.paths import templates


router = APIRouter()

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

# Chunk size for bulk CSV imports. Keeps memory bounded on large files.
_IMPORT_CHUNK = 1000


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
        request,
        "index.html",
        {
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
        request,
        "search.html",
        {
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
        request,
        "detail.html",
        {
            "etab": etab,
            "ej": ej,
            "autres_et": autres_et,
        },
    )


@router.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return templates.TemplateResponse(
        request,
        "import.html",
        {"max_upload_mb": settings.max_upload_mb},
    )


async def _spool_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Lit le fichier en streaming et refuse tout ce qui dépasse la limite."""
    buf = io.BytesIO()
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop volumineux (> {max_bytes // (1024 * 1024)} Mo).",
            )
        buf.write(chunk)
    return buf.getvalue()


def _import_dataframe(df: pd.DataFrame, model, db: Session) -> int:
    """Insère / met à jour un DataFrame dans la table `model`.

    Utilise `bulk_*_mappings` par lot pour limiter la pression mémoire et
    les aller-retours SQL.
    """
    cols = set(model.__table__.columns.keys())
    pk = model.__table__.primary_key.columns.values()[0].name

    df.columns = [c.strip().lower() for c in df.columns]
    if pk not in df.columns:
        raise ValueError(f"Colonne clé '{pk}' absente du fichier.")

    keep = [c for c in df.columns if c in cols]
    df = df[keep].copy()
    df = df[df[pk].notna() & (df[pk].astype(str).str.strip() != "")]

    # Qui existe déjà, pour dispatcher INSERT vs UPDATE sans ORM Objects.
    existing_ids = {
        row[0]
        for row in db.query(getattr(model, pk)).filter(
            getattr(model, pk).in_(df[pk].tolist())
        )
    }

    inserts = []
    updates = []
    for record in df.to_dict(orient="records"):
        if record[pk] in existing_ids:
            updates.append(record)
        else:
            inserts.append(record)

    for i in range(0, len(inserts), _IMPORT_CHUNK):
        db.bulk_insert_mappings(model, inserts[i : i + _IMPORT_CHUNK])
    for i in range(0, len(updates), _IMPORT_CHUNK):
        db.bulk_update_mappings(model, updates[i : i + _IMPORT_CHUNK])

    return len(inserts) + len(updates)


@router.post("/import", response_class=HTMLResponse)
async def import_data(
    request: Request,
    fichier_et: UploadFile = File(..., description="Fichier CSV des établissements"),
    fichier_ej: Optional[UploadFile] = File(
        None, description="Fichier CSV des entités juridiques"
    ),
    db: Session = Depends(get_db),
):
    messages: list[str] = []
    errors: list[str] = []
    max_bytes = settings.max_upload_bytes

    try:
        if fichier_ej and fichier_ej.filename:
            payload = await _spool_upload(fichier_ej, max_bytes)
            df_ej = pd.read_csv(io.BytesIO(payload), sep=";", dtype=str, encoding="utf-8")
            count = _import_dataframe(df_ej, EntiteJuridique, db)
            db.commit()
            messages.append(f"{count} entité(s) juridique(s) importée(s).")
            logger.info("Import EJ : %d rows", count)

        payload = await _spool_upload(fichier_et, max_bytes)
        df_et = pd.read_csv(io.BytesIO(payload), sep=";", dtype=str, encoding="utf-8")
        count = _import_dataframe(df_et, Etablissement, db)
        db.commit()
        messages.append(f"{count} établissement(s) importé(s).")
        logger.info("Import ET : %d rows", count)

    except HTTPException:
        raise
    except UnicodeDecodeError as exc:
        db.rollback()
        errors.append(f"Encodage invalide (attendu UTF-8) : {exc}")
        logger.warning("Import rejeté : encodage invalide")
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        db.rollback()
        errors.append(f"Fichier CSV invalide : {exc}")
        logger.warning("Import rejeté : parse error (%s)", exc)
    except ValueError as exc:
        db.rollback()
        errors.append(str(exc))
        logger.warning("Import rejeté : %s", exc)
    except SQLAlchemyError as exc:
        db.rollback()
        errors.append("Erreur base de données pendant l'import.")
        logger.exception("Import: erreur SQLAlchemy : %s", exc)

    return templates.TemplateResponse(
        request,
        "import.html",
        {
            "messages": messages,
            "errors": errors,
            "max_upload_mb": settings.max_upload_mb,
        },
    )
