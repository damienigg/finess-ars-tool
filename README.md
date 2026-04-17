# FINESS ARS - Outil d'assistance

Outil web d'aide à la gestion du répertoire FINESS pour les Agences Régionales de Santé (ARS).

## Fonctionnalités

- **Tableau de bord** : vue synthétique du parc d'établissements (ET/EJ), répartition par région et catégorie
- **Recherche** : recherche multicritères (N° FINESS, nom, commune, code postal, région, département, catégorie) avec pagination
- **Fiche établissement** : détail complet d'un ET, lien vers l'EJ, liste des autres ET de la même EJ
- **Import CSV** : chargement des extractions FINESS (fichiers ET et EJ au format CSV séparateur `;`)

## Stack technique

- **Backend** : Python 3.12 / FastAPI / SQLAlchemy
- **Frontend** : Jinja2 + Bootstrap 5
- **Base de données** : SQLite (locale)

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
uvicorn app.main:app --reload
```

Puis ouvrir http://127.0.0.1:8000

## Données

Les fichiers d'extraction FINESS (CSV) sont disponibles sur [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/finess-extraction-du-fichier-des-etablissements/).

Utilisez la page **Import** de l'application pour charger les fichiers ET et EJ.
