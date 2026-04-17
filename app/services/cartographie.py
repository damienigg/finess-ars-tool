"""Service de cartographie — conversion de coordonnées et analyse spatiale."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Etablissement


# ---------------------------------------------------------------------------
# Conversion Lambert 93 → WGS84
# ---------------------------------------------------------------------------

def lambert93_to_wgs84(x: float, y: float) -> Tuple[float, float]:
    """Convertit des coordonnées Lambert 93 (EPSG:2154) en WGS84 (lat, lon).

    Utilise pyproj si disponible, sinon une approximation.
    """
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(x, y)
        return (lat, lon)
    except ImportError:
        # Approximation grossière pour la France métropolitaine
        lon = (x - 600000) / 111320 / math.cos(math.radians(46.5)) + 2.0
        lat = (y - 6000000) / 110540 + 46.0
        return (lat, lon)


@dataclass
class PointEtablissement:
    nofinesset: str
    rs: str
    categetab: str
    libcategetab: str
    lat: float
    lon: float
    commune: str
    departement: str


def get_etablissements_geolocalises(db: Session, **filtres) -> List[PointEtablissement]:
    """Récupère les ET géolocalisés avec conversion en WGS84."""
    query = db.query(Etablissement).filter(
        Etablissement.coordxet.isnot(None),
        Etablissement.coordyet.isnot(None),
        Etablissement.coordxet != "",
        Etablissement.coordyet != "",
    )

    if filtres.get("region"):
        query = query.filter(Etablissement.region == filtres["region"])
    if filtres.get("departement"):
        query = query.filter(Etablissement.departement == filtres["departement"])
    if filtres.get("categetab"):
        query = query.filter(Etablissement.categetab == filtres["categetab"])

    points = []
    for et in query.all():
        try:
            x = float(et.coordxet)
            y = float(et.coordyet)
        except (ValueError, TypeError):
            continue
        if x == 0 and y == 0:
            continue
        lat, lon = lambert93_to_wgs84(x, y)
        points.append(PointEtablissement(
            nofinesset=et.nofinesset,
            rs=et.rs or "",
            categetab=et.categetab or "",
            libcategetab=et.libcategetab or "",
            lat=lat,
            lon=lon,
            commune=et.libcommune or "",
            departement=et.departement or "",
        ))
    return points


# ---------------------------------------------------------------------------
# Détection d'anomalies géographiques
# ---------------------------------------------------------------------------

# Bounding boxes approximatives par département (quelques exemples)
DEPT_BOUNDS: Dict[str, Tuple[float, float, float, float]] = {
    # dept: (lat_min, lat_max, lon_min, lon_max)
    "75": (48.81, 48.91, 2.22, 2.47),
    "13": (43.15, 43.75, 4.15, 5.82),
    "69": (45.45, 46.00, 4.25, 5.05),
    "31": (42.87, 43.92, 0.44, 2.05),
    "33": (44.19, 45.58, -1.26, 0.32),
}


def detecter_coordonnees_aberrantes(db: Session) -> List[Dict]:
    """Détecte les ET dont les coordonnées sont suspectes.

    - Coordonnées à (0, 0)
    - Coordonnées hors France métropolitaine
    - Coordonnées hors du département déclaré (si bbox connue)
    """
    anomalies = []
    for et in db.query(Etablissement).filter(
        Etablissement.coordxet.isnot(None),
        Etablissement.coordyet.isnot(None),
        Etablissement.coordxet != "",
        Etablissement.coordyet != "",
    ).all():
        try:
            x = float(et.coordxet)
            y = float(et.coordyet)
        except (ValueError, TypeError):
            anomalies.append({
                "nofinesset": et.nofinesset,
                "type": "COORD_NON_NUMERIQUE",
                "message": f"Coordonnées non numériques : x={et.coordxet}, y={et.coordyet}",
            })
            continue

        if x == 0 and y == 0:
            anomalies.append({
                "nofinesset": et.nofinesset,
                "type": "COORD_ZERO",
                "message": "Coordonnées à (0, 0)",
            })
            continue

        lat, lon = lambert93_to_wgs84(x, y)

        # Hors France métropolitaine élargie
        if not (41.0 <= lat <= 51.5 and -5.5 <= lon <= 10.0):
            anomalies.append({
                "nofinesset": et.nofinesset,
                "type": "COORD_HORS_FRANCE",
                "message": f"Coordonnées hors France métro : lat={lat:.4f}, lon={lon:.4f}",
            })
            continue

        # Hors bbox du département
        dept = et.departement
        if dept in DEPT_BOUNDS:
            lat_min, lat_max, lon_min, lon_max = DEPT_BOUNDS[dept]
            if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                anomalies.append({
                    "nofinesset": et.nofinesset,
                    "type": "COORD_HORS_DEPT",
                    "message": (
                        f"Coordonnées ({lat:.4f}, {lon:.4f}) hors du département "
                        f"{dept} déclaré"
                    ),
                })

    return anomalies


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre deux points GPS."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def zones_blanches(
    db: Session, categetab: str, rayon_km: float = 30.0
) -> List[PointEtablissement]:
    """Identifie les ET les plus isolés d'une catégorie donnée.

    Retourne les ET dont le plus proche voisin de même catégorie est > rayon_km.
    """
    points = get_etablissements_geolocalises(db, categetab=categetab)
    isoles = []

    for i, p in enumerate(points):
        min_dist = float("inf")
        for j, q in enumerate(points):
            if i == j:
                continue
            d = haversine_km(p.lat, p.lon, q.lat, q.lon)
            if d < min_dist:
                min_dist = d
        if min_dist > rayon_km:
            isoles.append(p)

    return isoles
