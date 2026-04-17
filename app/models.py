from sqlalchemy import Column, String, Integer, Date, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


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
