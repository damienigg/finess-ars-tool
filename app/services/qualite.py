"""Service de contrôle qualité — détection d'anomalies sur les données FINESS."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Anomalie, Etablissement, EntiteJuridique, NiveauAnomalie,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def valider_siret(siret: str) -> bool:
    """Vérifie un SIRET via l'algorithme de Luhn."""
    if not siret or not re.match(r"^\d{14}$", siret):
        return False
    total = 0
    for i, ch in enumerate(siret):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def valider_code_postal_departement(code_postal: str | None, departement: str | None) -> bool:
    """Vérifie la cohérence entre code postal et département."""
    if not code_postal or not departement:
        return True  # pas de données → pas d'incohérence détectable
    cp = code_postal.strip()
    dept = departement.strip()
    if dept in ("2A", "2B"):
        return cp.startswith("20")
    if len(dept) == 3 and dept.startswith("97"):
        return cp.startswith(dept)
    if len(dept) == 2:
        return cp[:2] == dept
    return True


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Ratio de similarité basé sur la distance de Levenshtein."""
    try:
        from Levenshtein import ratio
        return ratio(s1, s2)
    except ImportError:
        # Fallback naïf
        if s1 == s2:
            return 1.0
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        common = sum(c1 == c2 for c1, c2 in zip(s1, s2))
        return common / max_len


# ---------------------------------------------------------------------------
# Règles de contrôle
# ---------------------------------------------------------------------------

def regle_et_orphelins(db: Session) -> List[Dict]:
    """ET dont le nofinessej ne correspond à aucune EJ."""
    results = (
        db.query(Etablissement)
        .outerjoin(EntiteJuridique, Etablissement.nofinessej == EntiteJuridique.nofinesset)
        .filter(
            Etablissement.nofinessej.isnot(None),
            Etablissement.nofinessej != "",
            EntiteJuridique.nofinesset.is_(None),
        )
        .all()
    )
    return [
        {
            "nofinesset": e.nofinesset,
            "regle": "ET_ORPHELIN",
            "niveau": NiveauAnomalie.ERREUR.value,
            "message": f"ET {e.nofinesset} référence l'EJ {e.nofinessej} qui n'existe pas",
            "detail": f"EJ référencée : {e.nofinessej}",
        }
        for e in results
    ]


def regle_ej_sans_et(db: Session) -> List[Dict]:
    """EJ sans aucun ET rattaché (coquilles vides)."""
    subq = db.query(Etablissement.nofinessej).filter(Etablissement.nofinessej.isnot(None)).distinct()
    results = db.query(EntiteJuridique).filter(~EntiteJuridique.nofinesset.in_(subq)).all()
    return [
        {
            "nofinessej": ej.nofinesset,
            "regle": "EJ_SANS_ET",
            "niveau": NiveauAnomalie.AVERTISSEMENT.value,
            "message": f"EJ {ej.nofinesset} ({ej.rs}) n'a aucun ET rattaché",
        }
        for ej in results
    ]


def regle_siret_invalide(db: Session) -> List[Dict]:
    """ET ou EJ avec un SIRET qui ne passe pas le contrôle de Luhn."""
    anomalies = []
    for et in db.query(Etablissement).filter(
        Etablissement.siret.isnot(None), Etablissement.siret != ""
    ).all():
        if not valider_siret(et.siret):
            anomalies.append({
                "nofinesset": et.nofinesset,
                "regle": "SIRET_INVALIDE",
                "niveau": NiveauAnomalie.ERREUR.value,
                "message": f"SIRET invalide ({et.siret}) pour ET {et.nofinesset}",
                "detail": et.siret,
            })
    for ej in db.query(EntiteJuridique).filter(
        EntiteJuridique.siret.isnot(None), EntiteJuridique.siret != ""
    ).all():
        if not valider_siret(ej.siret):
            anomalies.append({
                "nofinessej": ej.nofinesset,
                "regle": "SIRET_INVALIDE",
                "niveau": NiveauAnomalie.ERREUR.value,
                "message": f"SIRET invalide ({ej.siret}) pour EJ {ej.nofinesset}",
                "detail": ej.siret,
            })
    return anomalies


def regle_cp_departement_incoherent(db: Session) -> List[Dict]:
    """Code postal incohérent avec le département."""
    anomalies = []
    for et in db.query(Etablissement).filter(
        Etablissement.codepostal.isnot(None), Etablissement.departement.isnot(None)
    ).all():
        if not valider_code_postal_departement(et.codepostal, et.departement):
            anomalies.append({
                "nofinesset": et.nofinesset,
                "regle": "CP_DEPT_INCOHERENT",
                "niveau": NiveauAnomalie.ERREUR.value,
                "message": (
                    f"CP {et.codepostal} incohérent avec département {et.departement} "
                    f"pour ET {et.nofinesset}"
                ),
                "detail": f"CP={et.codepostal}, Dept={et.departement}",
            })
    return anomalies


def regle_adresse_incomplete(db: Session) -> List[Dict]:
    """ET sans adresse exploitable."""
    anomalies = []
    for et in db.query(Etablissement).all():
        missing = []
        if not et.voie and not et.numvoie:
            missing.append("voie")
        if not et.codepostal:
            missing.append("code postal")
        if not et.libcommune:
            missing.append("commune")
        if missing:
            anomalies.append({
                "nofinesset": et.nofinesset,
                "regle": "ADRESSE_INCOMPLETE",
                "niveau": NiveauAnomalie.AVERTISSEMENT.value,
                "message": f"Adresse incomplète pour ET {et.nofinesset} : {', '.join(missing)} manquant(s)",
                "detail": ", ".join(missing),
            })
    return anomalies


def regle_ouvert_sans_autorisation(db: Session) -> List[Dict]:
    """ET ouvert depuis > 2 ans sans date d'autorisation."""
    anomalies = []
    deux_ans = datetime.utcnow() - timedelta(days=730)
    for et in db.query(Etablissement).filter(
        Etablissement.dateouv.isnot(None),
        Etablissement.dateouv != "",
    ).all():
        if et.dateautor and et.dateautor.strip():
            continue
        try:
            date_ouv = datetime.strptime(et.dateouv.strip(), "%Y-%m-%d")
        except (ValueError, AttributeError):
            continue
        if date_ouv < deux_ans:
            anomalies.append({
                "nofinesset": et.nofinesset,
                "regle": "OUVERT_SANS_AUTORISATION",
                "niveau": NiveauAnomalie.AVERTISSEMENT.value,
                "message": (
                    f"ET {et.nofinesset} ouvert le {et.dateouv} sans date d'autorisation"
                ),
            })
    return anomalies


def regle_doublons_potentiels(db: Session, seuil: float = 0.85) -> List[Dict]:
    """Détecte les doublons potentiels (même commune, raison sociale proche)."""
    anomalies = []
    seen: set[Tuple[str, str]] = set()

    etabs_par_commune: Dict[str, List] = {}
    for et in db.query(Etablissement).filter(Etablissement.commune.isnot(None)).all():
        etabs_par_commune.setdefault(et.commune, []).append(et)

    for commune, etabs in etabs_par_commune.items():
        for i in range(len(etabs)):
            for j in range(i + 1, len(etabs)):
                a, b = etabs[i], etabs[j]
                if not a.rs or not b.rs:
                    continue
                pair_key = tuple(sorted([a.nofinesset, b.nofinesset]))
                if pair_key in seen:
                    continue
                ratio = _levenshtein_ratio(a.rs.upper(), b.rs.upper())
                if ratio >= seuil:
                    seen.add(pair_key)
                    anomalies.append({
                        "nofinesset": a.nofinesset,
                        "regle": "DOUBLON_POTENTIEL",
                        "niveau": NiveauAnomalie.AVERTISSEMENT.value,
                        "message": (
                            f"Doublon potentiel : {a.nofinesset} ({a.rs}) ↔ "
                            f"{b.nofinesset} ({b.rs}) — similarité {ratio:.0%}"
                        ),
                        "detail": f"{b.nofinesset}|{ratio:.2f}",
                    })
    return anomalies


def regle_siret_duplique(db: Session) -> List[Dict]:
    """SIRET identique utilisé par des entités distinctes."""
    anomalies = []
    dupes = (
        db.query(Etablissement.siret, func.count(Etablissement.nofinesset))
        .filter(Etablissement.siret.isnot(None), Etablissement.siret != "")
        .group_by(Etablissement.siret)
        .having(func.count(Etablissement.nofinesset) > 1)
        .all()
    )
    for siret, count in dupes:
        etabs = db.query(Etablissement).filter(Etablissement.siret == siret).all()
        ids = ", ".join(e.nofinesset for e in etabs)
        anomalies.append({
            "regle": "SIRET_DUPLIQUE",
            "niveau": NiveauAnomalie.AVERTISSEMENT.value,
            "message": f"SIRET {siret} partagé par {count} ET : {ids}",
            "detail": ids,
        })
    return anomalies


# ---------------------------------------------------------------------------
# Orchestrateur
# ---------------------------------------------------------------------------

ALL_RULES = [
    regle_et_orphelins,
    regle_ej_sans_et,
    regle_siret_invalide,
    regle_cp_departement_incoherent,
    regle_adresse_incomplete,
    regle_ouvert_sans_autorisation,
    regle_doublons_potentiels,
    regle_siret_duplique,
]


def executer_controle_qualite(db: Session) -> List[Anomalie]:
    """Exécute toutes les règles et persiste les anomalies."""
    # Purge les anciennes anomalies non résolues
    db.query(Anomalie).filter(Anomalie.resolved == False).delete()
    db.flush()

    toutes: List[Anomalie] = []
    for rule_fn in ALL_RULES:
        for raw in rule_fn(db):
            anomalie = Anomalie(
                nofinesset=raw.get("nofinesset"),
                nofinessej=raw.get("nofinessej"),
                regle=raw["regle"],
                niveau=raw["niveau"],
                message=raw["message"],
                detail=raw.get("detail"),
            )
            db.add(anomalie)
            toutes.append(anomalie)

    db.commit()
    return toutes


def score_qualite(db: Session) -> Dict:
    """Calcule un score de qualité global et par département."""
    total_et = db.query(func.count(Etablissement.nofinesset)).scalar() or 0
    total_anomalies = db.query(func.count(Anomalie.id)).filter(Anomalie.resolved == False).scalar() or 0

    if total_et == 0:
        score_global = 100.0
    else:
        score_global = max(0.0, 100.0 * (1 - total_anomalies / total_et))

    par_dept = (
        db.query(
            Etablissement.departement,
            Etablissement.libdepartement,
            func.count(Anomalie.id),
        )
        .outerjoin(Anomalie, Anomalie.nofinesset == Etablissement.nofinesset)
        .filter((Anomalie.resolved == False) | (Anomalie.id.is_(None)))
        .group_by(Etablissement.departement, Etablissement.libdepartement)
        .all()
    )

    par_regle = (
        db.query(Anomalie.regle, Anomalie.niveau, func.count(Anomalie.id))
        .filter(Anomalie.resolved == False)
        .group_by(Anomalie.regle, Anomalie.niveau)
        .order_by(func.count(Anomalie.id).desc())
        .all()
    )

    return {
        "score_global": round(score_global, 1),
        "total_et": total_et,
        "total_anomalies": total_anomalies,
        "par_departement": par_dept,
        "par_regle": par_regle,
    }
