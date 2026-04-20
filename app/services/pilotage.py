"""Service de pilotage — indicateurs et tableaux de bord."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Etablissement, EntiteJuridique, Dossier, Anomalie,
    StatutDemande,
)
from app.utils import utcnow


@dataclass
class IndicateursGlobaux:
    total_et: int
    total_ej: int
    total_dossiers_ouverts: int
    total_anomalies: int
    taux_completude: float  # % d'ET avec tous les champs clés remplis


def calculer_indicateurs_globaux(db: Session) -> IndicateursGlobaux:
    total_et = db.query(func.count(Etablissement.nofinesset)).scalar() or 0
    total_ej = db.query(func.count(EntiteJuridique.nofinesset)).scalar() or 0

    statuts_ouverts = [
        StatutDemande.RECU.value,
        StatutDemande.EN_INSTRUCTION.value,
        StatutDemande.ATTENTE_PIECE.value,
    ]
    total_dossiers_ouverts = (
        db.query(func.count(Dossier.id))
        .filter(Dossier.statut.in_(statuts_ouverts))
        .scalar()
        or 0
    )
    total_anomalies = (
        db.query(func.count(Anomalie.id))
        .filter(Anomalie.resolved == False)
        .scalar()
        or 0
    )

    # Complétude : on vérifie les champs clés
    champs_cles = ["rs", "categetab", "codepostal", "libcommune", "departement", "region"]
    if total_et > 0:
        complets = 0
        for et in db.query(Etablissement).all():
            ok = all(
                getattr(et, c) and str(getattr(et, c)).strip()
                for c in champs_cles
            )
            if ok:
                complets += 1
        taux_completude = round(100.0 * complets / total_et, 1)
    else:
        taux_completude = 0.0

    return IndicateursGlobaux(
        total_et=total_et,
        total_ej=total_ej,
        total_dossiers_ouverts=total_dossiers_ouverts,
        total_anomalies=total_anomalies,
        taux_completude=taux_completude,
    )


def repartition_par_categorie(db: Session) -> List[Dict]:
    rows = (
        db.query(
            Etablissement.categetab,
            Etablissement.libcategetab,
            func.count(Etablissement.nofinesset),
        )
        .group_by(Etablissement.categetab, Etablissement.libcategetab)
        .order_by(func.count(Etablissement.nofinesset).desc())
        .all()
    )
    return [
        {"code": code, "libelle": lib or "Non renseigné", "count": cnt}
        for code, lib, cnt in rows
    ]


def repartition_par_departement(db: Session) -> List[Dict]:
    rows = (
        db.query(
            Etablissement.departement,
            Etablissement.libdepartement,
            func.count(Etablissement.nofinesset),
        )
        .group_by(Etablissement.departement, Etablissement.libdepartement)
        .order_by(Etablissement.departement)
        .all()
    )
    return [
        {"code": dept, "libelle": lib or "Non renseigné", "count": cnt}
        for dept, lib, cnt in rows
    ]


def dossiers_par_statut(db: Session) -> List[Dict]:
    rows = (
        db.query(Dossier.statut, func.count(Dossier.id))
        .group_by(Dossier.statut)
        .all()
    )
    return [{"statut": statut, "count": cnt} for statut, cnt in rows]


def dossiers_en_retard(db: Session) -> List[Dossier]:
    """Dossiers ouverts dont la date d'échéance est dépassée."""
    statuts_ouverts = [
        StatutDemande.RECU.value,
        StatutDemande.EN_INSTRUCTION.value,
        StatutDemande.ATTENTE_PIECE.value,
    ]
    return (
        db.query(Dossier)
        .filter(
            Dossier.statut.in_(statuts_ouverts),
            Dossier.date_echeance.isnot(None),
            Dossier.date_echeance < utcnow(),
        )
        .order_by(Dossier.date_echeance)
        .all()
    )


def comparaison_inter_departementale(db: Session) -> List[Dict]:
    """Comparaison nombre ET et anomalies par département."""
    et_par_dept = dict(
        db.query(Etablissement.departement, func.count(Etablissement.nofinesset))
        .group_by(Etablissement.departement)
        .all()
    )

    anomalies_par_dept = {}
    for nofinesset, dept in db.query(Anomalie.nofinesset, Etablissement.departement).join(
        Etablissement, Anomalie.nofinesset == Etablissement.nofinesset
    ).filter(Anomalie.resolved == False).all():
        anomalies_par_dept[dept] = anomalies_par_dept.get(dept, 0) + 1

    result = []
    for dept, nb_et in sorted(et_par_dept.items()):
        nb_anom = anomalies_par_dept.get(dept, 0)
        taux = round(100.0 * nb_anom / nb_et, 1) if nb_et > 0 else 0.0
        result.append({
            "departement": dept,
            "nb_et": nb_et,
            "nb_anomalies": nb_anom,
            "taux_anomalies": taux,
        })
    return result
