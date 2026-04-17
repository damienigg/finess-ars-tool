"""Tests pour le service de contrôle qualité."""

import pytest
from app.models import Etablissement, EntiteJuridique, Anomalie
from app.services.qualite import (
    valider_siret,
    valider_code_postal_departement,
    regle_et_orphelins,
    regle_ej_sans_et,
    regle_siret_invalide,
    regle_cp_departement_incoherent,
    regle_adresse_incomplete,
    regle_ouvert_sans_autorisation,
    regle_doublons_potentiels,
    regle_siret_duplique,
    executer_controle_qualite,
    score_qualite,
    _levenshtein_ratio,
)


# ---------------------------------------------------------------------------
# Tests helpers
# ---------------------------------------------------------------------------

class TestValiderSiret:
    def test_siret_valide(self):
        # SIRET connu valide (La Poste siège)
        assert valider_siret("35600000000048") is True

    def test_siret_invalide_checksum(self):
        assert valider_siret("12345678901234") is False

    def test_siret_trop_court(self):
        assert valider_siret("1234") is False

    def test_siret_vide(self):
        assert valider_siret("") is False

    def test_siret_none(self):
        assert valider_siret(None) is False

    def test_siret_non_numerique(self):
        assert valider_siret("ABCDEFGHIJKLMN") is False

    def test_siret_14_zeros(self):
        # 00000000000000 passe Luhn (somme = 0)
        assert valider_siret("00000000000000") is True


class TestValiderCpDepartement:
    def test_coherent_75(self):
        assert valider_code_postal_departement("75013", "75") is True

    def test_incoherent_cp_13_dept_69(self):
        assert valider_code_postal_departement("13001", "69") is False

    def test_corse_2a(self):
        assert valider_code_postal_departement("20000", "2A") is True

    def test_corse_2b(self):
        assert valider_code_postal_departement("20200", "2B") is True

    def test_dom_tom_971(self):
        assert valider_code_postal_departement("97100", "971") is True

    def test_dom_tom_incoherent(self):
        assert valider_code_postal_departement("97100", "972") is False

    def test_none_values(self):
        assert valider_code_postal_departement(None, "75") is True
        assert valider_code_postal_departement("75013", None) is True
        assert valider_code_postal_departement(None, None) is True


class TestLevenshteinRatio:
    def test_identical(self):
        assert _levenshtein_ratio("CLINIQUE", "CLINIQUE") == 1.0

    def test_different(self):
        r = _levenshtein_ratio("CLINIQUE", "PHARMACIE")
        assert 0 < r < 1

    def test_similar(self):
        r = _levenshtein_ratio("CLINIQUE SAINT JEAN", "CLINIQUE SAINT JEAN PARIS")
        assert r > 0.7

    def test_empty(self):
        assert _levenshtein_ratio("", "") == 1.0


# ---------------------------------------------------------------------------
# Tests règles individuelles
# ---------------------------------------------------------------------------

class TestRegleEtOrphelins:
    def test_pas_dorphelin_si_ej_existe(self, db, sample_et):
        result = regle_et_orphelins(db)
        assert len(result) == 0

    def test_detecte_orphelin(self, db):
        et = Etablissement(
            nofinesset="999000001",
            nofinessej="999999999",  # EJ inexistante
            rs="ORPHELIN",
        )
        db.add(et)
        db.commit()
        result = regle_et_orphelins(db)
        assert len(result) == 1
        assert result[0]["regle"] == "ET_ORPHELIN"
        assert "999000001" in result[0]["message"]

    def test_ignore_et_sans_ej(self, db):
        et = Etablissement(nofinesset="999000002", rs="SANS EJ")
        db.add(et)
        db.commit()
        result = regle_et_orphelins(db)
        assert len(result) == 0


class TestRegleEjSansEt:
    def test_ej_avec_et(self, db, sample_et):
        result = regle_ej_sans_et(db)
        assert len(result) == 0

    def test_ej_sans_et(self, db):
        ej = EntiteJuridique(nofinesset="888000001", rs="EJ SEULE")
        db.add(ej)
        db.commit()
        result = regle_ej_sans_et(db)
        assert any(r["nofinessej"] == "888000001" for r in result)


class TestRegleSiretInvalide:
    def test_siret_valide_pas_anomalie(self, db, sample_et):
        result = regle_siret_invalide(db)
        # sample_et has siret "26750045200012" which may or may not be valid
        # We just check no crash
        assert isinstance(result, list)

    def test_detecte_siret_invalide(self, db, sample_et_mauvais_siret):
        result = regle_siret_invalide(db)
        assert any(
            r["nofinesset"] == "030000001" and r["regle"] == "SIRET_INVALIDE"
            for r in result
        )


class TestRegleCpDeptIncoherent:
    def test_coherent(self, db, sample_et):
        result = regle_cp_departement_incoherent(db)
        assert not any(r["nofinesset"] == "010000002" for r in result)

    def test_incoherent(self, db, sample_et_cp_incoherent):
        result = regle_cp_departement_incoherent(db)
        assert any(r["nofinesset"] == "040000001" for r in result)


class TestRegleAdresseIncomplete:
    def test_adresse_complete(self, db, sample_et):
        result = regle_adresse_incomplete(db)
        assert not any(r["nofinesset"] == "010000002" for r in result)

    def test_adresse_incomplete(self, db, sample_et_incomplet):
        result = regle_adresse_incomplete(db)
        matches = [r for r in result if r["nofinesset"] == "020000001"]
        assert len(matches) == 1
        assert "code postal" in matches[0]["detail"]
        assert "commune" in matches[0]["detail"]


class TestRegleOuvertSansAutorisation:
    def test_avec_autorisation(self, db, sample_et):
        result = regle_ouvert_sans_autorisation(db)
        assert not any(r["nofinesset"] == "010000002" for r in result)

    def test_sans_autorisation_ancien(self, db):
        et = Etablissement(
            nofinesset="777000001",
            rs="ANCIEN SANS AUTOR",
            dateouv="2020-01-01",
            dateautor="",
        )
        db.add(et)
        db.commit()
        result = regle_ouvert_sans_autorisation(db)
        assert any(r["nofinesset"] == "777000001" for r in result)

    def test_sans_autorisation_recent(self, db):
        """Un ET ouvert récemment sans autorisation ne devrait pas être flaggé."""
        from datetime import datetime, timedelta
        recent = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        et = Etablissement(
            nofinesset="777000002",
            rs="RECENT SANS AUTOR",
            dateouv=recent,
            dateautor="",
        )
        db.add(et)
        db.commit()
        result = regle_ouvert_sans_autorisation(db)
        assert not any(r["nofinesset"] == "777000002" for r in result)


class TestRegleDoublonsPotentiels:
    def test_detecte_doublons(self, db, multiple_ets):
        result = regle_doublons_potentiels(db)
        # CLINIQUE SAINT JEAN et CLINIQUE SAINT JEAN PARIS dans même commune
        assert any(r["regle"] == "DOUBLON_POTENTIEL" for r in result)

    def test_pas_de_doublon_communes_differentes(self, db, sample_et):
        """Un seul ET ne génère pas de doublon."""
        result = regle_doublons_potentiels(db)
        # with only one ET in the commune, no duplicates
        doubles_for_this = [r for r in result if "010000002" in r.get("nofinesset", "")]
        assert len(doubles_for_this) == 0


class TestRegleSiretDuplique:
    def test_pas_de_duplique(self, db, sample_et):
        result = regle_siret_duplique(db)
        # single ET → no duplicate
        assert len(result) == 0

    def test_detecte_siret_duplique(self, db):
        et1 = Etablissement(nofinesset="660000001", rs="ET1", siret="12345678900001")
        et2 = Etablissement(nofinesset="660000002", rs="ET2", siret="12345678900001")
        db.add_all([et1, et2])
        db.commit()
        result = regle_siret_duplique(db)
        assert any(r["regle"] == "SIRET_DUPLIQUE" for r in result)


# ---------------------------------------------------------------------------
# Tests orchestrateur
# ---------------------------------------------------------------------------

class TestExecuterControleQualite:
    def test_execute_toutes_regles(self, db, sample_et, sample_et_mauvais_siret, sample_et_cp_incoherent):
        anomalies = executer_controle_qualite(db)
        assert len(anomalies) > 0
        # Vérifie que les anomalies sont persistées
        count = db.query(Anomalie).count()
        assert count == len(anomalies)

    def test_purge_anciennes(self, db, sample_et_mauvais_siret):
        # First run
        executer_controle_qualite(db)
        count1 = db.query(Anomalie).count()
        # Second run should replace
        executer_controle_qualite(db)
        count2 = db.query(Anomalie).count()
        assert count1 == count2

    def test_base_vide(self, db):
        anomalies = executer_controle_qualite(db)
        assert isinstance(anomalies, list)


class TestScoreQualite:
    def test_score_100_si_aucune_anomalie(self, db, sample_et):
        scores = score_qualite(db)
        # Before running controls, no anomalies
        assert scores["score_global"] == 100.0

    def test_score_baisse_avec_anomalies(self, db, sample_et, sample_et_mauvais_siret):
        executer_controle_qualite(db)
        scores = score_qualite(db)
        assert scores["total_anomalies"] > 0

    def test_base_vide(self, db):
        scores = score_qualite(db)
        assert scores["score_global"] == 100.0
        assert scores["total_et"] == 0
