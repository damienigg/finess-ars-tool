"""Service de réconciliation — diff entre extractions, croisement SIRENE."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Etablissement, EntiteJuridique


# ---------------------------------------------------------------------------
# Diff entre deux extractions CSV
# ---------------------------------------------------------------------------

@dataclass
class DiffResult:
    """Résultat d'une comparaison entre deux fichiers FINESS."""
    ajoutes: List[str] = field(default_factory=list)
    supprimes: List[str] = field(default_factory=list)
    modifies: List[Dict] = field(default_factory=list)

    @property
    def total_changements(self) -> int:
        return len(self.ajoutes) + len(self.supprimes) + len(self.modifies)


def diff_extractions(csv_ancien: bytes, csv_nouveau: bytes, sep: str = ";") -> DiffResult:
    """Compare deux extractions CSV FINESS et retourne les différences.

    Les deux CSV doivent avoir une colonne 'nofinesset' comme clé.
    """
    df_old = pd.read_csv(io.BytesIO(csv_ancien), sep=sep, dtype=str, keep_default_na=False)
    df_new = pd.read_csv(io.BytesIO(csv_nouveau), sep=sep, dtype=str, keep_default_na=False)

    df_old.columns = [c.strip().lower() for c in df_old.columns]
    df_new.columns = [c.strip().lower() for c in df_new.columns]

    if "nofinesset" not in df_old.columns or "nofinesset" not in df_new.columns:
        raise ValueError("Les fichiers CSV doivent contenir une colonne 'nofinesset'")

    old_ids: Set[str] = set(df_old["nofinesset"].dropna().unique())
    new_ids: Set[str] = set(df_new["nofinesset"].dropna().unique())

    result = DiffResult()
    result.ajoutes = sorted(new_ids - old_ids)
    result.supprimes = sorted(old_ids - new_ids)

    # Champs modifiés pour les ET présents dans les deux
    communs = old_ids & new_ids
    common_cols = sorted(set(df_old.columns) & set(df_new.columns) - {"nofinesset"})

    old_indexed = df_old.set_index("nofinesset")
    new_indexed = df_new.set_index("nofinesset")

    for finess_id in sorted(communs):
        if finess_id not in old_indexed.index or finess_id not in new_indexed.index:
            continue
        old_row = old_indexed.loc[finess_id]
        new_row = new_indexed.loc[finess_id]

        # Handle potential duplicates in index (DataFrame vs Series)
        if isinstance(old_row, pd.DataFrame):
            old_row = old_row.iloc[0]
        if isinstance(new_row, pd.DataFrame):
            new_row = new_row.iloc[0]

        changes = {}
        for col in common_cols:
            old_val = str(old_row.get(col, "") if isinstance(old_row, pd.Series) else old_row).strip()
            new_val = str(new_row.get(col, "") if isinstance(new_row, pd.Series) else new_row).strip()
            if old_val != new_val:
                changes[col] = {"ancien": old_val, "nouveau": new_val}

        if changes:
            result.modifies.append({
                "nofinesset": finess_id,
                "changements": changes,
            })

    return result


# ---------------------------------------------------------------------------
# Vérification SIRENE via API INSEE
# ---------------------------------------------------------------------------

async def verifier_siret_sirene(siret: str, client=None) -> Dict:
    """Interroge l'API SIRENE pour vérifier un SIRET.

    Retourne un dict avec 'existe', 'actif', 'denomination', 'erreur'.
    """
    import httpx

    if not siret or len(siret) != 14:
        return {"existe": False, "actif": False, "erreur": "SIRET invalide (longueur)"}

    url = f"https://api.insee.fr/entreprises/sirene/V3.11/siret/{siret}"
    headers = {"Accept": "application/json"}

    http_client = client or httpx.AsyncClient()
    try:
        resp = await http_client.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return {"existe": False, "actif": False, "erreur": None}
        if resp.status_code == 403:
            return {"existe": None, "actif": None, "erreur": "Accès refusé (token requis)"}
        if resp.status_code != 200:
            return {"existe": None, "actif": None, "erreur": f"HTTP {resp.status_code}"}

        data = resp.json()
        etab = data.get("etablissement", {})
        periode = etab.get("periodesEtablissement", [{}])[0] if etab.get("periodesEtablissement") else {}
        return {
            "existe": True,
            "actif": periode.get("etatAdministratifEtablissement") == "A",
            "denomination": etab.get("uniteLegale", {}).get("denominationUniteLegale", ""),
            "erreur": None,
        }
    except httpx.HTTPError as e:
        return {"existe": None, "actif": None, "erreur": str(e)}
    finally:
        if client is None:
            await http_client.aclose()


def comparer_avec_sae(
    db: Session, csv_sae: bytes, sep: str = ";", col_finess: str = "nofinesset"
) -> Dict:
    """Compare la base FINESS locale avec une extraction SAE.

    Retourne les ET présents dans SAE mais pas FINESS, et inversement.
    """
    df_sae = pd.read_csv(io.BytesIO(csv_sae), sep=sep, dtype=str, keep_default_na=False)
    df_sae.columns = [c.strip().lower() for c in df_sae.columns]

    if col_finess.lower() not in df_sae.columns:
        raise ValueError(f"Colonne '{col_finess}' absente du fichier SAE")

    sae_ids: Set[str] = set(df_sae[col_finess.lower()].dropna().unique())

    finess_ids: Set[str] = {
        row[0] for row in db.query(Etablissement.nofinesset).all()
    }

    return {
        "dans_sae_pas_finess": sorted(sae_ids - finess_ids),
        "dans_finess_pas_sae": sorted(finess_ids - sae_ids),
        "communs": len(sae_ids & finess_ids),
        "total_sae": len(sae_ids),
        "total_finess": len(finess_ids),
    }
