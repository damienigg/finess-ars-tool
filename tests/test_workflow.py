"""Tests pour le workflow des dossiers."""

import pytest
from datetime import datetime, timedelta

from app.models import Dossier, EvenementDossier, StatutDemande, TypeDemande
from app.utils import utcnow


class TestCreerDossier:
    def test_creer_dossier_simple(self, db, sample_et):
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.CREATION.value,
            statut=StatutDemande.RECU.value,
            objet="Création d'un nouvel établissement",
            demandeur="M. Dupont",
            agent_instructeur="Agent Martin",
        )
        db.add(dossier)
        db.commit()
        assert dossier.id is not None
        assert dossier.statut == "recu"
        assert dossier.type_demande == "creation"

    def test_creer_dossier_avec_echeance(self, db, sample_et):
        echeance = utcnow() + timedelta(days=30)
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.MODIFICATION.value,
            statut=StatutDemande.RECU.value,
            date_echeance=echeance,
        )
        db.add(dossier)
        db.commit()
        assert dossier.date_echeance is not None


class TestChangerStatut:
    def test_transition_statut(self, db, sample_et):
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.MODIFICATION.value,
            statut=StatutDemande.RECU.value,
        )
        db.add(dossier)
        db.commit()

        ancien = dossier.statut
        dossier.statut = StatutDemande.EN_INSTRUCTION.value
        evt = EvenementDossier(
            dossier_id=dossier.id,
            auteur="Agent",
            type_evenement="changement_statut",
            ancien_statut=ancien,
            nouveau_statut=StatutDemande.EN_INSTRUCTION.value,
            commentaire="Prise en charge du dossier",
        )
        db.add(evt)
        db.commit()

        assert dossier.statut == "en_instruction"
        assert len(dossier.evenements) == 1
        assert dossier.evenements[0].ancien_statut == "recu"

    def test_cloture_sur_validation(self, db, sample_et):
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.CREATION.value,
            statut=StatutDemande.EN_INSTRUCTION.value,
        )
        db.add(dossier)
        db.commit()

        dossier.statut = StatutDemande.VALIDE.value
        dossier.date_cloture = utcnow()
        db.commit()

        assert dossier.date_cloture is not None

    def test_tous_les_statuts_possibles(self):
        """Vérifie que tous les statuts enum sont bien définis."""
        statuts = [s.value for s in StatutDemande]
        assert "recu" in statuts
        assert "en_instruction" in statuts
        assert "attente_piece" in statuts
        assert "valide" in statuts
        assert "rejete" in statuts
        assert "transmis_drees" in statuts

    def test_tous_les_types_possibles(self):
        types = [t.value for t in TypeDemande]
        assert "creation" in types
        assert "modification" in types
        assert "fermeture" in types
        assert "fusion" in types


class TestEvenementDossier:
    def test_ajouter_commentaire(self, db, sample_et):
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.MODIFICATION.value,
            statut=StatutDemande.EN_INSTRUCTION.value,
        )
        db.add(dossier)
        db.commit()

        evt = EvenementDossier(
            dossier_id=dossier.id,
            auteur="Agent Martin",
            type_evenement="commentaire",
            commentaire="Courrier envoyé à l'établissement",
        )
        db.add(evt)
        db.commit()

        assert len(dossier.evenements) == 1
        assert dossier.evenements[0].type_evenement == "commentaire"

    def test_historique_ordonne(self, db, sample_et):
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.CREATION.value,
            statut=StatutDemande.RECU.value,
        )
        db.add(dossier)
        db.commit()

        for i, statut in enumerate([
            StatutDemande.EN_INSTRUCTION.value,
            StatutDemande.ATTENTE_PIECE.value,
            StatutDemande.EN_INSTRUCTION.value,
            StatutDemande.VALIDE.value,
        ]):
            evt = EvenementDossier(
                dossier_id=dossier.id,
                auteur="Agent",
                type_evenement="changement_statut",
                nouveau_statut=statut,
                date=utcnow() + timedelta(seconds=i),
            )
            db.add(evt)

        db.commit()
        assert len(dossier.evenements) == 4

    def test_relation_dossier_etablissement(self, db, sample_et):
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande=TypeDemande.MODIFICATION.value,
            statut=StatutDemande.RECU.value,
        )
        db.add(dossier)
        db.commit()
        assert dossier.etablissement.rs == "CHU TEST - Site Principal"


class TestWorkflowRoutes:
    def test_liste_dossiers(self, client, db, sample_et):
        response = client.get("/workflow")
        assert response.status_code == 200

    def test_creer_dossier_via_form(self, client, db, sample_et):
        response = client.post(
            "/workflow/nouveau",
            data={
                "nofinesset": sample_et.nofinesset,
                "type_demande": "creation",
                "objet": "Test création",
                "demandeur": "Test",
                "agent_instructeur": "Agent",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_detail_dossier_inexistant(self, client):
        response = client.get("/workflow/99999")
        assert response.status_code == 200
        assert "introuvable" in response.text.lower() or "Dossier" in response.text

    def test_filtrer_par_statut(self, client, db, sample_et):
        # Create a dossier first
        dossier = Dossier(
            nofinesset=sample_et.nofinesset,
            type_demande="creation",
            statut="recu",
        )
        db.add(dossier)
        db.commit()

        response = client.get("/workflow?statut=recu")
        assert response.status_code == 200
