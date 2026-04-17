"""Tests pour le service de réconciliation."""

import pytest
from app.services.reconciliation import diff_extractions, DiffResult, comparer_avec_sae
from app.models import Etablissement


def _make_csv(rows, sep=";"):
    """Fabrique un CSV bytes à partir d'une liste de dicts."""
    if not rows:
        return b"nofinesset\n"
    cols = list(rows[0].keys())
    lines = [sep.join(cols)]
    for row in rows:
        lines.append(sep.join(str(row.get(c, "")) for c in cols))
    return "\n".join(lines).encode("utf-8")


# ---------------------------------------------------------------------------
# Tests diff_extractions
# ---------------------------------------------------------------------------

class TestDiffExtractions:
    def test_identique(self):
        csv_data = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU", "codepostal": "75013"},
        ])
        result = diff_extractions(csv_data, csv_data)
        assert result.total_changements == 0
        assert result.ajoutes == []
        assert result.supprimes == []
        assert result.modifies == []

    def test_ajout(self):
        ancien = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU"},
        ])
        nouveau = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU"},
            {"nofinesset": "010000002", "rs": "CLINIQUE"},
        ])
        result = diff_extractions(ancien, nouveau)
        assert "010000002" in result.ajoutes
        assert len(result.supprimes) == 0

    def test_suppression(self):
        ancien = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU"},
            {"nofinesset": "010000002", "rs": "CLINIQUE"},
        ])
        nouveau = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU"},
        ])
        result = diff_extractions(ancien, nouveau)
        assert "010000002" in result.supprimes
        assert len(result.ajoutes) == 0

    def test_modification(self):
        ancien = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU ANCIEN NOM", "codepostal": "75013"},
        ])
        nouveau = _make_csv([
            {"nofinesset": "010000001", "rs": "CHU NOUVEAU NOM", "codepostal": "75013"},
        ])
        result = diff_extractions(ancien, nouveau)
        assert len(result.modifies) == 1
        m = result.modifies[0]
        assert m["nofinesset"] == "010000001"
        assert "rs" in m["changements"]
        assert m["changements"]["rs"]["ancien"] == "CHU ANCIEN NOM"
        assert m["changements"]["rs"]["nouveau"] == "CHU NOUVEAU NOM"

    def test_ajout_suppression_modification_combines(self):
        ancien = _make_csv([
            {"nofinesset": "001", "rs": "A", "cp": "75000"},
            {"nofinesset": "002", "rs": "B", "cp": "69000"},
        ])
        nouveau = _make_csv([
            {"nofinesset": "001", "rs": "A MODIFIE", "cp": "75000"},
            {"nofinesset": "003", "rs": "C", "cp": "13000"},
        ])
        result = diff_extractions(ancien, nouveau)
        assert "003" in result.ajoutes
        assert "002" in result.supprimes
        assert any(m["nofinesset"] == "001" for m in result.modifies)

    def test_csv_sans_colonne_nofinesset(self):
        csv_data = _make_csv([{"rs": "CHU", "cp": "75013"}])
        with pytest.raises(ValueError, match="nofinesset"):
            diff_extractions(csv_data, csv_data)

    def test_csv_vide(self):
        ancien = b"nofinesset;rs\n"
        nouveau = b"nofinesset;rs\n"
        result = diff_extractions(ancien, nouveau)
        assert result.total_changements == 0


class TestDiffResult:
    def test_total_changements(self):
        r = DiffResult(ajoutes=["1", "2"], supprimes=["3"], modifies=[{"nofinesset": "4"}])
        assert r.total_changements == 4

    def test_vide(self):
        r = DiffResult()
        assert r.total_changements == 0


# ---------------------------------------------------------------------------
# Tests comparaison SAE
# ---------------------------------------------------------------------------

class TestComparerAvecSae:
    def test_comparaison_simple(self, db, sample_et):
        sae_csv = _make_csv([
            {"nofinesset": "010000002"},  # existe dans FINESS
            {"nofinesset": "999999999"},  # n'existe pas
        ])
        result = comparer_avec_sae(db, sae_csv)
        assert result["communs"] == 1
        assert "999999999" in result["dans_sae_pas_finess"]
        assert sample_et.nofinesset not in result["dans_sae_pas_finess"]

    def test_sae_vide(self, db, sample_et):
        sae_csv = b"nofinesset\n"
        result = comparer_avec_sae(db, sae_csv)
        assert result["communs"] == 0
        assert result["total_sae"] == 0

    def test_finess_pas_dans_sae(self, db, sample_et):
        sae_csv = _make_csv([{"nofinesset": "999000001"}])
        result = comparer_avec_sae(db, sae_csv)
        assert sample_et.nofinesset in result["dans_finess_pas_sae"]

    def test_colonne_absente(self, db):
        sae_csv = _make_csv([{"rs": "TEST"}])
        with pytest.raises(ValueError, match="nofinesset"):
            comparer_avec_sae(db, sae_csv)
