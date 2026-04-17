"""Tests pour le service de cartographie."""

import pytest
import math
from app.services.cartographie import (
    lambert93_to_wgs84,
    get_etablissements_geolocalises,
    detecter_coordonnees_aberrantes,
    haversine_km,
    zones_blanches,
)
from app.models import Etablissement


class TestLambert93ToWgs84:
    def test_paris_approximation(self):
        """Test avec les coordonnées approximatives de Paris."""
        # Paris : x≈652000, y≈6862000 en Lambert 93
        lat, lon = lambert93_to_wgs84(652000, 6862000)
        # Paris est environ à lat 48.85, lon 2.35
        assert 48.0 < lat < 49.5, f"Latitude {lat} hors de la fourchette attendue"
        assert 1.5 < lon < 3.5, f"Longitude {lon} hors de la fourchette attendue"

    def test_marseille_approximation(self):
        # Marseille : x≈893000, y≈6245000
        lat, lon = lambert93_to_wgs84(893000, 6245000)
        assert 42.5 < lat < 44.0
        assert 4.5 < lon < 6.5

    def test_retourne_tuple(self):
        result = lambert93_to_wgs84(600000, 6000000)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestHaversineKm:
    def test_meme_point(self):
        assert haversine_km(48.85, 2.35, 48.85, 2.35) == 0.0

    def test_paris_lyon(self):
        # Paris-Lyon ≈ 390-470 km
        d = haversine_km(48.8566, 2.3522, 45.7640, 4.8357)
        assert 380 < d < 480

    def test_symetrique(self):
        d1 = haversine_km(48.85, 2.35, 43.30, 5.37)
        d2 = haversine_km(43.30, 5.37, 48.85, 2.35)
        assert abs(d1 - d2) < 0.01

    def test_courte_distance(self):
        # Environ 1 km
        d = haversine_km(48.85, 2.35, 48.859, 2.35)
        assert 0.5 < d < 2.0


class TestGetEtablissementsGeolocalises:
    def test_retourne_points(self, db, sample_et):
        points = get_etablissements_geolocalises(db)
        assert len(points) >= 1
        p = points[0]
        assert p.nofinesset == "010000002"
        assert isinstance(p.lat, float)
        assert isinstance(p.lon, float)

    def test_filtre_par_departement(self, db, sample_et, multiple_ets):
        points_75 = get_etablissements_geolocalises(db, departement="75")
        points_13 = get_etablissements_geolocalises(db, departement="13")
        # sample_et is in 75 and has coords
        finess_75 = {p.nofinesset for p in points_75}
        assert "010000002" in finess_75

    def test_ignore_coords_vides(self, db, sample_et_incomplet):
        points = get_etablissements_geolocalises(db)
        finess_ids = {p.nofinesset for p in points}
        assert "020000001" not in finess_ids  # no coords

    def test_ignore_coords_zero(self, db):
        et = Etablissement(
            nofinesset="770000001", rs="ZERO", coordxet="0", coordyet="0",
            departement="75",
        )
        db.add(et)
        db.commit()
        points = get_etablissements_geolocalises(db)
        assert not any(p.nofinesset == "770000001" for p in points)


class TestDetecterCoordonneesAberrantes:
    def test_coordonnees_normales(self, db, sample_et):
        anomalies = detecter_coordonnees_aberrantes(db)
        # sample_et has valid Paris coords
        assert not any(a["nofinesset"] == "010000002" and a["type"] == "COORD_HORS_FRANCE" for a in anomalies)

    def test_coordonnees_zero(self, db):
        et = Etablissement(
            nofinesset="880000001", rs="ZERO", coordxet="0", coordyet="0",
        )
        db.add(et)
        db.commit()
        anomalies = detecter_coordonnees_aberrantes(db)
        assert any(a["nofinesset"] == "880000001" and a["type"] == "COORD_ZERO" for a in anomalies)

    def test_coordonnees_non_numeriques(self, db):
        et = Etablissement(
            nofinesset="880000002", rs="BAD", coordxet="ABC", coordyet="DEF",
        )
        db.add(et)
        db.commit()
        anomalies = detecter_coordonnees_aberrantes(db)
        assert any(a["nofinesset"] == "880000002" and a["type"] == "COORD_NON_NUMERIQUE" for a in anomalies)


class TestZonesBlanches:
    def test_pas_de_zone_blanche_si_un_seul(self, db, sample_et):
        # With only one ET of category 355, it's automatically isolated
        isoles = zones_blanches(db, categetab="355", rayon_km=30.0)
        # Only one ET → no neighbor → infinite distance → isolated
        assert len(isoles) == 1

    def test_aucun_de_cette_categorie(self, db, sample_et):
        isoles = zones_blanches(db, categetab="999", rayon_km=30.0)
        assert len(isoles) == 0
