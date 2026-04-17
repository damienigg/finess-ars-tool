"""Service de génération de documents — courriers pré-remplis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List

from sqlalchemy.orm import Session

from app.models import Etablissement, EntiteJuridique, Dossier


# ---------------------------------------------------------------------------
# Modèles de courriers
# ---------------------------------------------------------------------------

@dataclass
class ModeleDocument:
    id: str
    nom: str
    description: str
    template: str  # template Jinja-like avec {{ variables }}


MODELES: Dict[str, ModeleDocument] = {
    "notification_immatriculation": ModeleDocument(
        id="notification_immatriculation",
        nom="Notification d'immatriculation FINESS",
        description="Notifie l'attribution d'un numéro FINESS à un établissement",
        template="""
AGENCE RÉGIONALE DE SANTÉ
{{ ars_nom }}

{{ ars_adresse }}

À {{ lieu }}, le {{ date }}

Objet : Notification d'immatriculation au répertoire FINESS

Madame, Monsieur,

J'ai l'honneur de vous informer que l'établissement désigné ci-après a été immatriculé
au répertoire national FINESS sous le numéro suivant :

    Numéro FINESS ET : {{ nofinesset }}
    Raison sociale : {{ rs }}
    Catégorie : {{ libcategetab }}
    Adresse : {{ adresse_complete }}

{% if nofinessej %}
Cet établissement est rattaché à l'entité juridique :
    Numéro FINESS EJ : {{ nofinessej }}
    Raison sociale EJ : {{ rs_ej }}
{% endif %}

Ce numéro doit être utilisé dans toutes vos correspondances avec les organismes
d'assurance maladie et les administrations sanitaires et sociales.

Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.

{{ signataire_nom }}
{{ signataire_titre }}
""",
    ),
    "demande_mise_a_jour": ModeleDocument(
        id="demande_mise_a_jour",
        nom="Demande de mise à jour des données",
        description="Demande à un établissement de vérifier et mettre à jour ses informations",
        template="""
AGENCE RÉGIONALE DE SANTÉ
{{ ars_nom }}

{{ ars_adresse }}

À {{ lieu }}, le {{ date }}

Objet : Demande de mise à jour de vos données FINESS

Madame, Monsieur le Directeur,

Dans le cadre de l'actualisation du répertoire FINESS, je vous prie de bien vouloir
vérifier et, le cas échéant, mettre à jour les informations relatives à votre
établissement :

    Numéro FINESS : {{ nofinesset }}
    Raison sociale : {{ rs }}
    Adresse actuelle : {{ adresse_complete }}
    Téléphone : {{ telephone }}
    Courriel : {{ courriel }}
    SIRET : {{ siret }}

Merci de nous retourner le formulaire ci-joint complété et signé dans un délai
de {{ delai_jours }} jours à compter de la réception du présent courrier.

{{ signataire_nom }}
{{ signataire_titre }}
""",
    ),
    "relance": ModeleDocument(
        id="relance",
        nom="Relance",
        description="Relance un établissement suite à une demande restée sans réponse",
        template="""
AGENCE RÉGIONALE DE SANTÉ
{{ ars_nom }}

{{ ars_adresse }}

À {{ lieu }}, le {{ date }}

Objet : RELANCE — {{ objet_initial }}

Référence dossier : {{ dossier_id }}

Madame, Monsieur,

Par courrier en date du {{ date_courrier_initial }}, nous vous demandions
{{ objet_initial }}.

À ce jour, nous n'avons pas reçu de réponse de votre part.

Nous vous prions de bien vouloir donner suite à cette demande dans les meilleurs
délais, et au plus tard sous {{ delai_jours }} jours.

À défaut de réponse, nous serons contraints de procéder d'office aux modifications
nécessaires.

{{ signataire_nom }}
{{ signataire_titre }}
""",
    ),
    "notification_fermeture": ModeleDocument(
        id="notification_fermeture",
        nom="Notification de fermeture",
        description="Notification de fermeture d'un établissement dans le répertoire FINESS",
        template="""
AGENCE RÉGIONALE DE SANTÉ
{{ ars_nom }}

{{ ars_adresse }}

À {{ lieu }}, le {{ date }}

Objet : Fermeture dans le répertoire FINESS

Madame, Monsieur,

J'ai l'honneur de vous informer que l'établissement ci-après a été fermé dans le
répertoire national FINESS à compter du {{ date_fermeture }} :

    Numéro FINESS : {{ nofinesset }}
    Raison sociale : {{ rs }}
    Adresse : {{ adresse_complete }}

Cette fermeture fait suite à {{ motif_fermeture }}.

{{ signataire_nom }}
{{ signataire_titre }}
""",
    ),
    "attestation_finess": ModeleDocument(
        id="attestation_finess",
        nom="Attestation FINESS",
        description="Attestation confirmant l'existence d'un établissement dans le répertoire FINESS",
        template="""
AGENCE RÉGIONALE DE SANTÉ
{{ ars_nom }}

{{ ars_adresse }}

À {{ lieu }}, le {{ date }}

ATTESTATION

Je soussigné(e), {{ signataire_nom }}, {{ signataire_titre }}, atteste que
l'établissement désigné ci-après figure au répertoire national FINESS :

    Numéro FINESS ET : {{ nofinesset }}
    Raison sociale : {{ rs }}
    Catégorie : {{ libcategetab }} ({{ categetab }})
    Adresse : {{ adresse_complete }}
    Date d'ouverture : {{ dateouv }}
{% if nofinessej %}
    Entité juridique : {{ nofinessej }} — {{ rs_ej }}
{% endif %}

La présente attestation est délivrée pour servir et valoir ce que de droit.

{{ signataire_nom }}
{{ signataire_titre }}
""",
    ),
}


# ---------------------------------------------------------------------------
# Fonctions de génération
# ---------------------------------------------------------------------------

def lister_modeles() -> List[ModeleDocument]:
    return list(MODELES.values())


def get_modele(modele_id: str) -> Optional[ModeleDocument]:
    return MODELES.get(modele_id)


def _adresse_complete(etab) -> str:
    parts = []
    if etab.numvoie:
        parts.append(etab.numvoie)
    if etab.typvoie:
        parts.append(etab.typvoie)
    if etab.voie:
        parts.append(etab.voie)
    ligne1 = " ".join(parts)
    ligne2 = f"{etab.codepostal or ''} {etab.libcommune or ''}".strip()
    return f"{ligne1}, {ligne2}" if ligne1 else ligne2


def generer_document(
    db: Session,
    modele_id: str,
    nofinesset: str,
    variables_extra: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Génère un document texte pré-rempli à partir d'un modèle et d'un ET.

    Retourne le texte du document, ou None si le modèle ou l'ET est introuvable.
    """
    modele = get_modele(modele_id)
    if not modele:
        return None

    etab = db.query(Etablissement).filter(Etablissement.nofinesset == nofinesset).first()
    if not etab:
        return None

    ej = None
    if etab.nofinessej:
        ej = db.query(EntiteJuridique).filter(
            EntiteJuridique.nofinesset == etab.nofinessej
        ).first()

    variables = {
        "nofinesset": etab.nofinesset,
        "nofinessej": etab.nofinessej or "",
        "rs": etab.rs or "",
        "rslongue": etab.rslongue or "",
        "categetab": etab.categetab or "",
        "libcategetab": etab.libcategetab or "",
        "adresse_complete": _adresse_complete(etab),
        "codepostal": etab.codepostal or "",
        "libcommune": etab.libcommune or "",
        "departement": etab.departement or "",
        "telephone": etab.telephone or "",
        "courriel": etab.courriel or "",
        "siret": etab.siret or "",
        "dateouv": etab.dateouv or "",
        "dateautor": etab.dateautor or "",
        "rs_ej": ej.rs if ej else "",
        "date": datetime.now().strftime("%d/%m/%Y"),
        # Defaults
        "ars_nom": "[Nom de l'ARS]",
        "ars_adresse": "[Adresse de l'ARS]",
        "lieu": "[Ville]",
        "signataire_nom": "[Nom du signataire]",
        "signataire_titre": "[Titre du signataire]",
        "delai_jours": "30",
        "date_courrier_initial": "[Date]",
        "objet_initial": "[Objet]",
        "dossier_id": "",
        "date_fermeture": "[Date]",
        "motif_fermeture": "[Motif]",
    }

    if variables_extra:
        variables.update(variables_extra)

    # Simple template rendering ({{ var }})
    text = modele.template
    for key, value in variables.items():
        text = text.replace("{{ " + key + " }}", value)
        text = text.replace("{{" + key + "}}", value)

    # Handle {% if var %} ... {% endif %} blocks
    import re
    pattern = r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}"
    def replace_if(match):
        var_name = match.group(1)
        content = match.group(2)
        if variables.get(var_name):
            return content
        return ""
    text = re.sub(pattern, replace_if, text, flags=re.DOTALL)

    return text.strip()
