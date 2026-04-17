"""Tests pour les routes principales (établissements, recherche, import)."""

import pytest


class TestIndex:
    def test_page_accueil(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "FINESS" in response.text

    def test_accueil_avec_donnees(self, client, db, sample_et, multiple_ets):
        response = client.get("/")
        assert response.status_code == 200


class TestRecherche:
    def test_page_recherche(self, client):
        response = client.get("/recherche")
        assert response.status_code == 200

    def test_recherche_par_nom(self, client, db, sample_et):
        response = client.get("/recherche?q=CHU")
        assert response.status_code == 200
        assert "CHU TEST" in response.text

    def test_recherche_par_finess(self, client, db, sample_et):
        response = client.get("/recherche?q=010000002")
        assert response.status_code == 200
        assert "010000002" in response.text

    def test_recherche_par_region(self, client, db, sample_et):
        response = client.get("/recherche?region=11")
        assert response.status_code == 200

    def test_recherche_par_departement(self, client, db, sample_et):
        response = client.get("/recherche?departement=75")
        assert response.status_code == 200

    def test_recherche_sans_resultat(self, client, db):
        response = client.get("/recherche?q=XXXXXXNOTFOUND")
        assert response.status_code == 200
        assert "Aucun" in response.text

    def test_recherche_pagination(self, client, db, multiple_ets):
        response = client.get("/recherche?page=1")
        assert response.status_code == 200


class TestDetailEtablissement:
    def test_detail_existant(self, client, db, sample_et):
        response = client.get("/etablissement/010000002")
        assert response.status_code == 200
        assert "CHU TEST - Site Principal" in response.text
        assert "010000001" in response.text  # EJ link

    def test_detail_inexistant(self, client, db):
        response = client.get("/etablissement/999999999")
        assert response.status_code == 200
        assert "non trouv" in response.text.lower()

    def test_detail_avec_autres_et(self, client, db, sample_et, multiple_ets):
        response = client.get(f"/etablissement/{sample_et.nofinesset}")
        assert response.status_code == 200
        # Les autres ET de la même EJ devraient apparaître
        assert "050000001" in response.text


class TestImport:
    def test_page_import(self, client):
        response = client.get("/import")
        assert response.status_code == 200
        assert "Import" in response.text


class TestQualiteRoutes:
    def test_page_qualite(self, client):
        response = client.get("/qualite")
        assert response.status_code == 200
        assert "qualite" in response.text.lower() or "Qualite" in response.text

    def test_lancer_controle(self, client, db, sample_et):
        response = client.post("/qualite/executer")
        assert response.status_code == 200

    def test_export_csv(self, client, db, sample_et):
        response = client.get("/qualite/export")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv") or "csv" in response.headers.get("content-disposition", "")


class TestReconciliationRoutes:
    def test_page_reconciliation(self, client):
        response = client.get("/reconciliation")
        assert response.status_code == 200
        assert "Reconciliation" in response.text


class TestCartographieRoutes:
    def test_page_carte(self, client):
        response = client.get("/cartographie")
        assert response.status_code == 200
        assert "map" in response.text.lower()

    def test_api_points(self, client, db, sample_et):
        response = client.get("/cartographie/api/points")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 1

    def test_api_points_filtre(self, client, db, sample_et):
        response = client.get("/cartographie/api/points?departement=75")
        assert response.status_code == 200
        data = response.json()
        assert all(
            f["properties"]["departement"] == "75"
            for f in data["features"]
        )

    def test_api_anomalies_geo(self, client, db, sample_et):
        response = client.get("/cartographie/api/anomalies-geo")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
