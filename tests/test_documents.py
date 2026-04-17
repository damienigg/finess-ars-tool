"""Tests pour le service de génération de documents."""

import pytest
from app.services.documents import (
    lister_modeles,
    get_modele,
    generer_document,
    MODELES,
    _adresse_complete,
)
from app.models import Etablissement


class TestListerModeles:
    def test_retourne_tous_les_modeles(self):
        modeles = lister_modeles()
        assert len(modeles) == len(MODELES)
        assert all(hasattr(m, "id") for m in modeles)

    def test_modeles_attendus(self):
        ids = {m.id for m in lister_modeles()}
        assert "notification_immatriculation" in ids
        assert "demande_mise_a_jour" in ids
        assert "relance" in ids
        assert "notification_fermeture" in ids
        assert "attestation_finess" in ids


class TestGetModele:
    def test_modele_existant(self):
        m = get_modele("notification_immatriculation")
        assert m is not None
        assert m.nom == "Notification d'immatriculation FINESS"

    def test_modele_inexistant(self):
        assert get_modele("inexistant") is None


class TestAdresseComplete:
    def test_adresse_complete(self):
        class FakeEtab:
            numvoie = "12"
            typvoie = "RUE"
            voie = "DE LA PAIX"
            codepostal = "75001"
            libcommune = "PARIS"

        result = _adresse_complete(FakeEtab())
        assert "12" in result
        assert "RUE" in result
        assert "DE LA PAIX" in result
        assert "75001" in result
        assert "PARIS" in result

    def test_adresse_sans_numvoie(self):
        class FakeEtab:
            numvoie = None
            typvoie = None
            voie = "AVENUE DES CHAMPS"
            codepostal = "75008"
            libcommune = "PARIS"

        result = _adresse_complete(FakeEtab())
        assert "AVENUE DES CHAMPS" in result

    def test_adresse_vide(self):
        class FakeEtab:
            numvoie = None
            typvoie = None
            voie = None
            codepostal = "75001"
            libcommune = "PARIS"

        result = _adresse_complete(FakeEtab())
        assert "75001" in result


class TestGenererDocument:
    def test_notification_immatriculation(self, db, sample_et):
        texte = generer_document(db, "notification_immatriculation", "010000002")
        assert texte is not None
        assert "010000002" in texte
        assert "CHU TEST - Site Principal" in texte
        assert "immatricul" in texte.lower()

    def test_demande_mise_a_jour(self, db, sample_et):
        texte = generer_document(db, "demande_mise_a_jour", "010000002")
        assert texte is not None
        assert "mise à jour" in texte.lower()
        assert "010000002" in texte

    def test_attestation_finess(self, db, sample_et):
        texte = generer_document(db, "attestation_finess", "010000002")
        assert texte is not None
        assert "ATTESTATION" in texte
        assert "010000002" in texte

    def test_notification_fermeture(self, db, sample_et):
        texte = generer_document(db, "notification_fermeture", "010000002")
        assert texte is not None
        assert "ferm" in texte.lower()

    def test_relance(self, db, sample_et):
        texte = generer_document(db, "relance", "010000002")
        assert texte is not None
        assert "RELANCE" in texte

    def test_avec_variables_extra(self, db, sample_et):
        texte = generer_document(
            db, "notification_immatriculation", "010000002",
            variables_extra={
                "ars_nom": "ARS Île-de-France",
                "lieu": "Paris",
                "signataire_nom": "Dr Martin",
                "signataire_titre": "Directeur général",
            },
        )
        assert "ARS Île-de-France" in texte
        assert "Dr Martin" in texte

    def test_modele_inexistant(self, db, sample_et):
        result = generer_document(db, "inexistant", "010000002")
        assert result is None

    def test_et_inexistant(self, db):
        result = generer_document(db, "notification_immatriculation", "999999999")
        assert result is None

    def test_avec_ej_rattachee(self, db, sample_et):
        """Vérifie que les infos EJ sont incluses quand disponibles."""
        texte = generer_document(db, "attestation_finess", "010000002")
        assert "010000001" in texte  # numéro EJ
        assert "CHU TEST" in texte  # raison sociale EJ

    def test_sans_ej(self, db, sample_et_incomplet):
        texte = generer_document(db, "attestation_finess", "020000001")
        assert texte is not None
        assert "LABO TEST" in texte


class TestDocumentsRoutes:
    def test_liste_modeles(self, client):
        response = client.get("/documents")
        assert response.status_code == 200
        assert "Notification" in response.text

    def test_formulaire_generer(self, client):
        response = client.get("/documents/generer?modele_id=notification_immatriculation")
        assert response.status_code == 200

    def test_generer_document(self, client, db, sample_et):
        response = client.post(
            "/documents/generer",
            data={
                "modele_id": "attestation_finess",
                "nofinesset": "010000002",
                "ars_nom": "ARS Test",
                "ars_adresse": "1 rue Test",
                "lieu": "Paris",
                "signataire_nom": "Test",
                "signataire_titre": "DG",
                "delai_jours": "30",
            },
        )
        assert response.status_code == 200
        assert "ATTESTATION" in response.text
