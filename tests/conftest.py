"""Fixtures partagées pour les tests."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import Etablissement, EntiteJuridique, Dossier, EvenementDossier, Anomalie


@pytest.fixture
def engine():
    """Moteur SQLite en mémoire pour les tests (StaticPool pour partage de connexion)."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    """Session de base de données de test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine):
    """Client HTTP de test avec base en mémoire."""
    Session = sessionmaker(bind=engine)

    def _get_test_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures de données
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ej(db):
    """Crée une entité juridique de test."""
    ej = EntiteJuridique(
        nofinesset="010000001",
        rs="CHU TEST",
        categetab="1101",
        libcategetab="Centre Hospitalier Régional",
        codepostal="75013",
        commune="75056",
        libcommune="PARIS",
        departement="75",
        libdepartement="Paris",
        region="11",
        libregion="Île-de-France",
        siret="26750045200012",
        dateouv="2010-01-01",
        dateautor="2010-06-01",
    )
    db.add(ej)
    db.commit()
    return ej


@pytest.fixture
def sample_et(db, sample_ej):
    """Crée un établissement de test rattaché à l'EJ."""
    et = Etablissement(
        nofinesset="010000002",
        nofinessej="010000001",
        rs="CHU TEST - Site Principal",
        categetab="355",
        libcategetab="Centre Hospitalier (C.H.)",
        codepostal="75013",
        commune="75056",
        libcommune="PARIS",
        departement="75",
        libdepartement="Paris",
        region="11",
        libregion="Île-de-France",
        numvoie="1",
        typvoie="RUE",
        voie="DE LA SANTE",
        siret="26750045200012",
        dateouv="2010-01-01",
        dateautor="2010-06-01",
        telephone="0145000000",
        courriel="contact@chu-test.fr",
        coordxet="652000",
        coordyet="6861000",
    )
    db.add(et)
    db.commit()
    return et


@pytest.fixture
def sample_et_incomplet(db):
    """Crée un ET avec des données manquantes."""
    et = Etablissement(
        nofinesset="020000001",
        rs="LABO TEST",
        categetab="611",
        libcategetab="Laboratoire",
        departement="75",
        # Pas de codepostal, pas de commune, pas de voie
    )
    db.add(et)
    db.commit()
    return et


@pytest.fixture
def sample_et_mauvais_siret(db):
    """ET avec un SIRET invalide."""
    et = Etablissement(
        nofinesset="030000001",
        rs="PHARMACIE TEST",
        categetab="620",
        libcategetab="Pharmacie",
        codepostal="69001",
        libcommune="LYON",
        departement="69",
        region="84",
        siret="12345678901234",  # invalide
        voie="RUE TEST",
    )
    db.add(et)
    db.commit()
    return et


@pytest.fixture
def sample_et_cp_incoherent(db):
    """ET dont le CP ne correspond pas au département."""
    et = Etablissement(
        nofinesset="040000001",
        rs="CLINIQUE ERREUR",
        categetab="365",
        libcategetab="Clinique",
        codepostal="13001",  # CP Marseille
        libcommune="LYON",
        departement="69",  # Dept Lyon
        region="84",
        voie="AVENUE DU BUG",
    )
    db.add(et)
    db.commit()
    return et


@pytest.fixture
def multiple_ets(db, sample_ej):
    """Crée plusieurs ET pour les tests de doublons et stats."""
    ets = [
        Etablissement(
            nofinesset="050000001",
            nofinessej="010000001",
            rs="CLINIQUE SAINT JEAN",
            categetab="365",
            libcategetab="Clinique",
            codepostal="75010",
            commune="75056",
            libcommune="PARIS",
            departement="75",
            libdepartement="Paris",
            region="11",
            libregion="Île-de-France",
            voie="RUE SAINT JEAN",
            siret="80295478500028",
        ),
        Etablissement(
            nofinesset="050000002",
            nofinessej="010000001",
            rs="CLINIQUE SAINT JEAN PARIS",  # doublon potentiel
            categetab="365",
            libcategetab="Clinique",
            codepostal="75010",
            commune="75056",
            libcommune="PARIS",
            departement="75",
            libdepartement="Paris",
            region="11",
            libregion="Île-de-France",
            voie="RUE SAINT JEAN BIS",
            siret="80295478500036",
        ),
        Etablissement(
            nofinesset="050000003",
            rs="EHPAD LES LILAS",
            categetab="500",
            libcategetab="EHPAD",
            codepostal="13001",
            commune="13055",
            libcommune="MARSEILLE",
            departement="13",
            libdepartement="Bouches-du-Rhône",
            region="93",
            libregion="Provence-Alpes-Côte d'Azur",
            voie="BOULEVARD DES LILAS",
            siret="44306184100025",
        ),
    ]
    db.add_all(ets)
    db.commit()
    return ets
