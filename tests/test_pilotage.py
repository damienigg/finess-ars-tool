"""Tests pour le service de pilotage."""

import pytest
from datetime import datetime, timedelta

from app.models import Dossier, Anomalie, StatutDemande
from app.services.pilotage import (
    calculer_indicateurs_globaux,
    repartition_par_categorie,
    repartition_par_departement,
    dossiers_par_statut,
    dossiers_en_retard,
    comparaison_inter_departementale,
)
from app.utils import utcnow


class TestIndicateursGlobaux:
    def test_base_vide(self, db):
        ind = calculer_indicateurs_globaux(db)
        assert ind.total_et == 0
        assert ind.total_ej == 0
        assert ind.total_dossiers_ouverts == 0
        assert ind.total_anomalies == 0
        assert ind.taux_completude == 0.0

    def test_avec_donnees(self, db, sample_et, sample_ej):
        ind = calculer_indicateurs_globaux(db)
        assert ind.total_et >= 1
        assert ind.total_ej >= 1

    def test_completude_100(self, db, sample_et):
        """sample_et a tous les champs clés remplis."""
        ind = calculer_indicateurs_globaux(db)
        # sample_et has rs, categetab, codepostal, libcommune, departement, region
        assert ind.taux_completude > 0

    def test_completude_partielle(self, db, sample_et, sample_et_incomplet):
        ind = calculer_indicateurs_globaux(db)
        # 1 complet + 1 incomplet = 50%
        assert 0 < ind.taux_completude < 100

    def test_dossiers_ouverts(self, db, sample_et):
        d1 = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande="creation",
            statut=StatutDemande.EN_INSTRUCTION.value,
        )
        d2 = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande="modification",
            statut=StatutDemande.VALIDE.value,  # fermé
        )
        db.add_all([d1, d2])
        db.commit()

        ind = calculer_indicateurs_globaux(db)
        assert ind.total_dossiers_ouverts == 1

    def test_anomalies_comptees(self, db, sample_et):
        a = Anomalie(
            nofinesset=sample_et.nofinesset,
            regle="TEST",
            niveau="erreur",
            message="Test anomalie",
            resolved=False,
        )
        db.add(a)
        db.commit()
        ind = calculer_indicateurs_globaux(db)
        assert ind.total_anomalies == 1


class TestRepartitionParCategorie:
    def test_base_vide(self, db):
        result = repartition_par_categorie(db)
        assert result == []

    def test_avec_donnees(self, db, sample_et, multiple_ets):
        result = repartition_par_categorie(db)
        assert len(result) > 0
        # Vérifie la structure
        assert all("code" in r and "libelle" in r and "count" in r for r in result)
        # Les cliniques (365) devraient avoir count >= 2
        cliniques = [r for r in result if r["code"] == "365"]
        assert len(cliniques) == 1
        assert cliniques[0]["count"] >= 2


class TestRepartitionParDepartement:
    def test_avec_donnees(self, db, sample_et, multiple_ets):
        result = repartition_par_departement(db)
        assert len(result) > 0
        depts = {r["code"] for r in result}
        assert "75" in depts


class TestDossiersParStatut:
    def test_vide(self, db):
        assert dossiers_par_statut(db) == []

    def test_avec_dossiers(self, db, sample_et):
        db.add(Dossier(nofinesset=sample_et.nofinesset, type_demande="creation", statut="recu"))
        db.add(Dossier(nofinesset=sample_et.nofinesset, type_demande="creation", statut="recu"))
        db.add(Dossier(nofinesset=sample_et.nofinesset, type_demande="creation", statut="valide"))
        db.commit()
        result = dossiers_par_statut(db)
        recu = [r for r in result if r["statut"] == "recu"]
        assert recu[0]["count"] == 2


class TestDossiersEnRetard:
    def test_aucun_retard(self, db, sample_et):
        future = utcnow() + timedelta(days=30)
        db.add(Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande="creation",
            statut="en_instruction",
            date_echeance=future,
        ))
        db.commit()
        retards = dossiers_en_retard(db)
        assert len(retards) == 0

    def test_detecte_retard(self, db, sample_et):
        passe = utcnow() - timedelta(days=5)
        db.add(Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande="modification",
            statut="en_instruction",
            date_echeance=passe,
        ))
        db.commit()
        retards = dossiers_en_retard(db)
        assert len(retards) == 1

    def test_ignore_dossiers_clos(self, db, sample_et):
        passe = utcnow() - timedelta(days=5)
        db.add(Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande="creation",
            statut="valide",  # clos
            date_echeance=passe,
        ))
        db.commit()
        retards = dossiers_en_retard(db)
        assert len(retards) == 0


class TestComparaisonInterDepartementale:
    def test_base_vide(self, db):
        result = comparaison_inter_departementale(db)
        assert result == []

    def test_avec_donnees(self, db, sample_et, multiple_ets):
        # Add an anomaly
        db.add(Anomalie(
            nofinesset=sample_et.nofinesset,
            regle="TEST", niveau="erreur", message="test", resolved=False,
        ))
        db.commit()
        result = comparaison_inter_departementale(db)
        assert len(result) > 0
        dept_75 = [r for r in result if r["departement"] == "75"]
        assert len(dept_75) == 1
        assert dept_75[0]["nb_anomalies"] >= 1


class TestPilotageRoutes:
    def test_page_pilotage(self, client):
        response = client.get("/pilotage")
        assert response.status_code == 200
        assert "Pilotage" in response.text

    def test_page_avec_donnees(self, client, db, sample_et, multiple_ets):
        response = client.get("/pilotage")
        assert response.status_code == 200
