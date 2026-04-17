from sqlalchemy import (
    Column, String, Integer, Float, Text, ForeignKey, DateTime, Enum, Boolean,
)
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TypeDemande(str, enum.Enum):
    CREATION = "creation"
    MODIFICATION = "modification"
    FERMETURE = "fermeture"
    FUSION = "fusion"


class StatutDemande(str, enum.Enum):
    RECU = "recu"
    EN_INSTRUCTION = "en_instruction"
    ATTENTE_PIECE = "attente_piece"
    VALIDE = "valide"
    REJETE = "rejete"
    TRANSMIS_DREES = "transmis_drees"


class NiveauAnomalie(str, enum.Enum):
    ERREUR = "erreur"
    AVERTISSEMENT = "avertissement"
    INFO = "info"


# ---------------------------------------------------------------------------
# FINESS core
# ---------------------------------------------------------------------------

class EntiteJuridique(Base):
    """Entité juridique (EJ) - l'organisme gestionnaire."""

    __tablename__ = "entites_juridiques"

    nofinesset = Column(String(9), primary_key=True, index=True)
    rs = Column(String(255), comment="Raison sociale")
    rslongue = Column(Text, comment="Raison sociale longue")
    categetab = Column(String(4), comment="Code catégorie")
    libcategetab = Column(String(255), comment="Libellé catégorie")
    numvoie = Column(String(10))
    typvoie = Column(String(10))
    voie = Column(String(255))
    compvoie = Column(String(255))
    compldistrib = Column(String(255))
    codepostal = Column(String(5))
    commune = Column(String(5), comment="Code commune INSEE")
    libcommune = Column(String(255))
    departement = Column(String(3))
    libdepartement = Column(String(255))
    region = Column(String(2), comment="Code région")
    libregion = Column(String(255))
    telephone = Column(String(20))
    telecopie = Column(String(20))
    courriel = Column(String(255))
    siret = Column(String(14))
    dateouv = Column(String(10), comment="Date d'ouverture")
    dateautor = Column(String(10), comment="Date d'autorisation")

    etablissements = relationship("Etablissement", back_populates="entite_juridique")


class Etablissement(Base):
    """Établissement (ET) - site géographique."""

    __tablename__ = "etablissements"

    nofinesset = Column(String(9), primary_key=True, index=True)
    nofinessej = Column(
        String(9), ForeignKey("entites_juridiques.nofinesset"), index=True
    )
    rs = Column(String(255), comment="Raison sociale")
    rslongue = Column(Text, comment="Raison sociale longue")
    categetab = Column(String(4), comment="Code catégorie")
    libcategetab = Column(String(255), comment="Libellé catégorie")
    categagretab = Column(String(4), comment="Code catégorie agrégée")
    libcategagretab = Column(String(255), comment="Libellé catégorie agrégée")
    numvoie = Column(String(10))
    typvoie = Column(String(10))
    voie = Column(String(255))
    compvoie = Column(String(255))
    compldistrib = Column(String(255))
    codepostal = Column(String(5))
    commune = Column(String(5), comment="Code commune INSEE")
    libcommune = Column(String(255))
    departement = Column(String(3))
    libdepartement = Column(String(255))
    region = Column(String(2), comment="Code région")
    libregion = Column(String(255))
    telephone = Column(String(20))
    telecopie = Column(String(20))
    courriel = Column(String(255))
    siret = Column(String(14))
    dateouv = Column(String(10), comment="Date d'ouverture")
    dateautor = Column(String(10), comment="Date d'autorisation")
    mft = Column(String(4), comment="Code mode de fixation des tarifs")
    libmft = Column(String(255), comment="Libellé MFT")
    sph = Column(String(4), comment="Code SPH")
    libsph = Column(String(255), comment="Libellé SPH")
    coordxet = Column(String(20), comment="Coordonnée X (Lambert 93)")
    coordyet = Column(String(20), comment="Coordonnée Y (Lambert 93)")

    entite_juridique = relationship("EntiteJuridique", back_populates="etablissements")
    dossiers = relationship("Dossier", back_populates="etablissement")
    anomalies = relationship("Anomalie", back_populates="etablissement")


# ---------------------------------------------------------------------------
# B. Workflow
# ---------------------------------------------------------------------------

class Dossier(Base):
    """Dossier de demande rattaché à un ET ou EJ."""

    __tablename__ = "dossiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nofinesset = Column(String(9), ForeignKey("etablissements.nofinesset"), index=True)
    nofinessej = Column(String(9), nullable=True)
    type_demande = Column(String(20), nullable=False)
    statut = Column(String(20), nullable=False, default=StatutDemande.RECU.value)
    objet = Column(Text, comment="Description de la demande")
    demandeur = Column(String(255))
    agent_instructeur = Column(String(255))
    date_reception = Column(DateTime, default=datetime.utcnow)
    date_echeance = Column(DateTime, nullable=True)
    date_cloture = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    etablissement = relationship("Etablissement", back_populates="dossiers")
    evenements = relationship(
        "EvenementDossier", back_populates="dossier", order_by="EvenementDossier.date"
    )


class EvenementDossier(Base):
    """Événement dans le cycle de vie d'un dossier."""

    __tablename__ = "evenements_dossier"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dossier_id = Column(Integer, ForeignKey("dossiers.id"), index=True)
    date = Column(DateTime, default=datetime.utcnow)
    auteur = Column(String(255))
    type_evenement = Column(String(50), comment="changement_statut, commentaire, piece_jointe")
    ancien_statut = Column(String(20), nullable=True)
    nouveau_statut = Column(String(20), nullable=True)
    commentaire = Column(Text, nullable=True)
    piece_jointe = Column(String(500), nullable=True)

    dossier = relationship("Dossier", back_populates="evenements")


# ---------------------------------------------------------------------------
# A. Anomalies / Contrôle qualité
# ---------------------------------------------------------------------------

class Anomalie(Base):
    """Anomalie détectée par le moteur de contrôle qualité."""

    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nofinesset = Column(String(9), ForeignKey("etablissements.nofinesset"), index=True, nullable=True)
    nofinessej = Column(String(9), nullable=True)
    regle = Column(String(50), nullable=False, comment="Identifiant de la règle")
    niveau = Column(String(20), nullable=False, default=NiveauAnomalie.ERREUR.value)
    message = Column(Text, nullable=False)
    detail = Column(Text, nullable=True)
    date_detection = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)

    etablissement = relationship("Etablissement", back_populates="anomalies")


# ---------------------------------------------------------------------------
# F. Historique des modifications (versioning)
# ---------------------------------------------------------------------------

class HistoriqueModification(Base):
    """Snapshot d'un champ modifié dans le temps."""

    __tablename__ = "historique_modifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entite_type = Column(String(2), comment="ET ou EJ")
    nofinesset = Column(String(9), index=True)
    champ = Column(String(50))
    ancienne_valeur = Column(Text, nullable=True)
    nouvelle_valeur = Column(Text, nullable=True)
    date_modification = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), comment="import, manuel, reconciliation")
