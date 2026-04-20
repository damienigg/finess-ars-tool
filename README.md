# Finess-for-Laure

Outil de gestion du répertoire FINESS. Installable en un clic sur Windows,
aucune compétence technique requise.

---

## 📥 Pour Laure : installation (3 minutes)

1. Aller sur la page des téléchargements :
   **https://github.com/damienigg/finess-ars-tool/releases/latest**
2. Cliquer sur **`Finess-for-Laure-Setup-x.y.z.exe`**.
3. Le fichier téléchargé : double-cliquer dessus.
   - Si Windows affiche un avertissement bleu, cliquer sur **Informations complémentaires** → **Exécuter quand même**. (Ça arrive tant que l'éditeur n'est pas signé, c'est normal, pas dangereux.)
4. Cliquer sur **Suivant → Installer → Terminer**.
5. Ouvrir **Finess-for-Laure** depuis le menu Démarrer (icône bleue hôpital).

La fenêtre de l'application s'ouvre automatiquement. Les données sont stockées
dans `%APPDATA%\Finess-for-Laure\` et ne quittent jamais l'ordinateur.

### Pour désinstaller

Panneau de configuration → Applications → **Finess-for-Laure** → Désinstaller.

---

## Fonctionnalités

- **Accueil** : synthèse du parc (ET/EJ), répartitions par région et catégorie
- **Recherche** multicritères (FINESS, nom, commune, région, département, catégorie)
- **Fiche établissement** : détail complet, EJ rattachée, raccourcis dossier/courrier
- **Import CSV** des extractions FINESS (ET + EJ)
- **Contrôle qualité** : 8 règles, score par département, export CSV
- **Dossiers** : kanban, création, statuts, commentaires, export CSV
- **Réconciliation** : diff d'extractions, comparaison FINESS/SAE, vérification SIRENE
- **Carte interactive** : anomalies géographiques, zones blanches par catégorie
- **Courriers** : 5 modèles pré-remplis (notification, mise à jour, relance, fermeture, attestation)
- **Pilotage** : indicateurs, comparaison inter-départementale, dossiers en retard, exports CSV

---

## Pour les développeurs

### Stack

Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Jinja2 · Bootstrap 5 · Leaflet ·
pywebview · PyInstaller.

### Dev local

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
# ouvrir http://127.0.0.1:8000
```

### Tests

```bash
pytest
```

143 tests, SQLite en mémoire.

### Build Windows local

```bash
pip install -r requirements-desktop.txt
pyinstaller --clean --noconfirm Finess-for-Laure.spec
# puis, avec Inno Setup installé :
iscc installer.iss
# → dist-installer\Finess-for-Laure-Setup-<version>.exe
```

### Publication d'une release

```bash
git tag v0.3.1
git push origin v0.3.1
```

La CI GitHub Actions construit automatiquement l'installeur Windows et
l'attache à la release sur https://github.com/damienigg/finess-ars-tool/releases.

### Serveur web (optionnel, pour un déploiement multi-utilisateurs)

```bash
docker compose up -d --build
```

Voir `docker-compose.yml` et `.env.example` pour les variables d'environnement.

### Variables d'environnement

| Variable | Défaut | Rôle |
|----------|--------|------|
| `DATABASE_URL` | auto (SQLite dans `%APPDATA%` en mode packagé, `./finess.db` en dev) | URL SQLAlchemy |
| `APP_ENV` | `development` | `development`, `staging`, `production` |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FILE` | auto | Fichier rotatif (10 Mo × 5) |
| `MAX_UPLOAD_MB` | `100` | Taille max des imports CSV |
| `SIRENE_API_BASE` | API INSEE V3.11 | |
| `SIRENE_API_TOKEN` | *(vide)* | Bearer INSEE (optionnel) |

---

## Données

Les extractions FINESS (CSV, séparateur `;`) se trouvent sur
[data.gouv.fr](https://www.data.gouv.fr/fr/datasets/finess-extraction-du-fichier-des-etablissements/).
Utiliser la page **Import** de l'application pour charger les fichiers.

## Sécurité

L'application est conçue pour un **usage mono-utilisateur local** (version
packagée) ou un **usage interne ARS derrière un reverse-proxy** (version
serveur). Aucune authentification intégrée. Toutes les requêtes base passent
par l'ORM (pas de SQL concaténé). Les templates Jinja2 sont auto-échappés.
