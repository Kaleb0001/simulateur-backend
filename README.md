<div align="center">

# Simulateur SFD : backend

![Python](https://img.shields.io/badge/3.14-3776AB?logo=python&logoColor=fff&label=Python&labelColor=333&color=3776AB&style=flat)
![PostgreSQL](https://img.shields.io/badge/16-4169E1?logo=postgresql&logoColor=fff&label=PostgreSQL&labelColor=333&color=4169E1&style=flat)
![FastAPI](https://img.shields.io/badge/0.141.1-009688?logo=fastapi&logoColor=fff&label=FastAPI&labelColor=333&color=009688&style=flat)

![Uvicorn](https://img.shields.io/badge/0.52.4-499848?logo=python&logoColor=fff&label=Uvicorn&labelColor=333&color=499848&style=flat)
![SQLAlchemy](https://img.shields.io/badge/2.0.52-D71F00?logo=sqlalchemy&logoColor=fff&label=SQLAlchemy&labelColor=333&color=D71F00&style=flat)
![psycopg](https://img.shields.io/badge/3.3.5-336791?logo=postgresql&logoColor=fff&label=psycopg&labelColor=333&color=336791&style=flat)
![Pydantic](https://img.shields.io/badge/2.13.5-E92063?logo=pydantic&logoColor=fff&label=Pydantic&labelColor=333&color=E92063&style=flat)
![pydantic-settings](https://img.shields.io/badge/2.15.0-E92063?logo=pydantic&logoColor=fff&label=pydantic-settings&labelColor=333&color=E92063&style=flat)
![HTTPX](https://img.shields.io/badge/0.28.1-4051B5?logo=python&logoColor=fff&label=HTTPX&labelColor=333&color=4051B5&style=flat)

API REST qui joue le rôle du **système de gestion interne d'un SFD** (système financier décentralisé) : **clients** et leur dossier KYC, **comptes**, **transactions** et **listes fermées**.
Un système tiers comme **IMF SHIELD** y lit les données avec un **jeton en lecture seule**, ou reçoit ses événements par **webhook signé**, via la passerelle n8n.

</div>

## 🎖️ Fonctionnalités

- **Dossier client complet** : identité, activité professionnelle, bénéficiaires effectifs, documents et auto-déclarations (PPE, sanctions), pour une personne physique comme pour une personne morale.
- **Comptes et opérations** : ouverture de comptes, dépôts, retraits et virements avec contrôle du solde ; un compte bloqué refuse toute opération.
- **Listes fermées** : agences, professions, tranches de revenus, sources des fonds et motifs de retrait, exposés avec leur code et leur libellé ; tout code inconnu est refusé.
- **Synchronisation incrémentale** : clients, comptes et transactions se filtrent sur `modifie_depuis`, pour ne relire que ce qui a changé.
- **Connexions de systèmes tiers** : un jeton en lecture seule, limité aux données choisies, et un abonnement webhook, créés en une requête et révocables.
- **Webhooks sortants** : chaque événement métier est envoyé en arrière-plan, signé en HMAC-SHA256, retenté en cas d'échec et renvoyable à la main.
- **Journal des accès** : chaque requête reçue est enregistrée avec le nom du consommateur.

## 📋 Prérequis

- **Python 3.14**.
- **PostgreSQL 16**, avec une base `simulateur_imf` et une base de test `simulateur_imf_test`. Dans l'espace de travail IMF SHIELD, le serveur Docker de `infra/postgres` les crée (port `5434`, utilisateur `simulateur`).
- **Docker Compose**, pour démarrer ce serveur.

Une URL SQLite reste acceptée pour un essai sans serveur ; la suite de tests, elle, exige PostgreSQL.

## 📦 Installation

```bash
# Récupérer le dépôt
git clone https://github.com/Kaleb0001/simulateur-backend.git
cd simulateur-backend

# Créer l'environnement virtuel et installer les dépendances, outils de test compris
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Créer la configuration, puis y renseigner DATABASE_URL et SIMULATEUR_API_TOKEN
cp .env.example .env

# Démarrer l'API sur http://localhost:8011
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Le schéma de la base est créé au premier démarrage. Les variables de configuration sont décrites dans `.env.example`.

Dans l'espace de travail IMF SHIELD, le dépôt est cloné dans `simulateur/backend` et `make demarrer s=simulateur-backend`, à la racine, le lance dans l'environnement partagé `simulateur/.venv-backend`.

## ⚙️ Utilisation

### 🚀 Documentation interactive

```bash
# Vérifier que l'API répond (sans jeton)
curl http://localhost:8011/
```

Swagger est servi sur http://localhost:8011/docs et décrit toutes les routes, leurs filtres et leurs schémas.

### 🔑 Authentification

Toutes les routes `/api/v1/…` exigent l'en-tête `Authorization: Bearer <jeton>`. Deux sortes de jetons sont acceptées :

- **`SIMULATEUR_API_TOKEN`**, le jeton d'administration du fichier `.env` : il a tous les droits ; c'est celui de l'interface du simulateur.
- **Le jeton d'une connexion tierce** : en lecture seule, il ne passe que les requêtes `GET`, sur les données cochées pour sa connexion (`403` sinon), et il est refusé (`401`) une fois la connexion révoquée.

```bash
# Lire les listes fermées avec le jeton d'administration
JETON=$(grep '^SIMULATEUR_API_TOKEN=' .env | cut -d= -f2-)
curl -H "Authorization: Bearer $JETON" http://localhost:8011/api/v1/referentiels
```

### 🔗 Connecter un système tiers

Une connexion regroupe un jeton en lecture seule (limité aux données listées dans `acces`) et un abonnement webhook vers `url_reception`. Le jeton et le secret de signature ne sont renvoyés qu'une fois, à la création ; perdus, on révoque la connexion et on en crée une nouvelle.

```bash
# Créer la connexion d'IMF SHIELD (passerelle n8n) et récupérer son jeton et son secret
curl -X POST http://localhost:8011/api/v1/connexions \
  -H "Authorization: Bearer $JETON" -H "Content-Type: application/json" \
  -d '{"nom": "IMF SHIELD", "url_reception": "http://localhost:5678/webhook/sfd/v1/events",
       "evenements": [], "acces": ["clients", "comptes", "transactions", "referentiels"]}'
```

Chaque livraison de webhook porte l'en-tête `X-Simulateur-Signature` (`sha256=` suivi du HMAC-SHA256 du corps avec le secret), que l'abonné recalcule pour vérifier l'origine.

### 🧪 Tests

```bash
# Lancer la suite de tests sur la base simulateur_imf_test
.venv/bin/pytest

# Désigner explicitement la base de test
TEST_DATABASE_URL="postgresql://simulateur:<mot de passe>@localhost:5434/simulateur_imf_test" .venv/bin/pytest
```

Sans `TEST_DATABASE_URL`, la base de test est déduite de `DATABASE_URL` en remplaçant le nom de la base. Ses tables sont supprimées puis recréées à chaque session ; par sécurité, seule une base dont le nom finit par `_test` est vidée.

## 🧰 Technologies et licences

Le code du simulateur (dossiers `app/`, `scripts/` et `tests/`) est écrit par l'équipe pour le hackathon. Il s'appuie sur les technologies et bibliothèques open source ci-dessous ; les licences des paquets Python sont celles de leurs métadonnées (`pip show <paquet>`).

| Technologie | Rôle | Licence |
|---|---|---|
| Python 3.14 | Langage et exécution de l'API | PSF (Python Software Foundation) |
| PostgreSQL 16 | Base de données | PostgreSQL License |
| FastAPI 0.141.1 | Cadre de l'API REST et documentation Swagger | MIT |
| Uvicorn 0.52.4 | Serveur ASGI qui sert l'application | BSD-3-Clause |
| SQLAlchemy 2.0.52 | ORM et accès à la base | MIT |
| psycopg 3.3.5 | Pilote PostgreSQL | LGPL-3.0-only |
| Pydantic 2.13.5 | Validation des schémas d'entrée et de sortie | MIT |
| pydantic-settings 2.15.0 | Lecture de la configuration (`.env`) | MIT |
| python-dotenv 1.2.3 | Chargement du fichier `.env` | BSD-3-Clause |
| HTTPX 0.28.1 | Client HTTP des envois de webhooks et des tests | BSD-3-Clause |
| pytest 8.4.2 | Suite de tests (`requirements-dev.txt`) | MIT |

## 🤝 Contribuer

Les tickets et les demandes de fusion sont les bienvenus sur le dépôt [Kaleb0001/simulateur-backend](https://github.com/Kaleb0001/simulateur-backend). Avant d'en proposer une, vérifiez que la suite de tests passe.

## 📜 Licence

Projet privé développé dans le cadre du hackathon ; aucune licence publique n'est accordée.
