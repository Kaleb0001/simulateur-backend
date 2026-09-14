<div align="center">

# simulateur-backend

![Python](https://img.shields.io/badge/3.14-3776AB?logo=python&logoColor=fff&label=Python&labelColor=333&color=3776AB&style=flat)
![PostgreSQL](https://img.shields.io/badge/16-4169E1?logo=postgresql&logoColor=fff&label=PostgreSQL&labelColor=333&color=4169E1&style=flat)
![FastAPI](https://img.shields.io/badge/0.141.1-009688?logo=fastapi&logoColor=fff&label=FastAPI&labelColor=333&color=009688&style=flat)
![Tests](https://img.shields.io/badge/82%20r%C3%A9ussis-3FB950?logo=pytest&logoColor=fff&label=Tests&labelColor=333&color=3FB950&style=flat)

![Uvicorn](https://img.shields.io/badge/0.52.4-499848?logo=python&logoColor=fff&label=Uvicorn&labelColor=333&color=499848&style=flat)
![SQLAlchemy](https://img.shields.io/badge/2.0.52-D71F00?logo=sqlalchemy&logoColor=fff&label=SQLAlchemy&labelColor=333&color=D71F00&style=flat)
![psycopg](https://img.shields.io/badge/3.3.5-336791?logo=postgresql&logoColor=fff&label=psycopg&labelColor=333&color=336791&style=flat)
![Pydantic](https://img.shields.io/badge/2.13.5-E92063?logo=pydantic&logoColor=fff&label=Pydantic&labelColor=333&color=E92063&style=flat)
![pydantic-settings](https://img.shields.io/badge/2.15.0-E92063?logo=pydantic&logoColor=fff&label=pydantic-settings&labelColor=333&color=E92063&style=flat)
![HTTPX](https://img.shields.io/badge/0.28.1-4051B5?logo=python&logoColor=fff&label=HTTPX&labelColor=333&color=4051B5&style=flat)
![python-dotenv](https://img.shields.io/badge/1.2.3-ECD53F?logo=dotenv&logoColor=fff&label=python-dotenv&labelColor=333&color=ECD53F&style=flat)

![Étoiles](https://img.shields.io/github/stars/Kaleb0001/simulateur-backend?logo=github&logoColor=fff&label=%C3%89toiles&labelColor=333&color=E3B341&style=flat)
![Forks](https://img.shields.io/github/forks/Kaleb0001/simulateur-backend?logo=github&logoColor=fff&label=Forks&labelColor=333&color=8957E5&style=flat)
![Abonnés](https://img.shields.io/github/watchers/Kaleb0001/simulateur-backend?logo=github&logoColor=fff&label=Abonn%C3%A9s&labelColor=333&color=1F6FEB&style=flat)
![Contributeurs](https://img.shields.io/github/contributors/Kaleb0001/simulateur-backend?logo=github&logoColor=fff&label=Contributeurs&labelColor=333&color=DB61A2&style=flat)
![Tickets ouverts](https://img.shields.io/github/issues-raw/Kaleb0001/simulateur-backend?logo=github&logoColor=fff&label=Tickets%20ouverts&labelColor=333&color=3FB950&style=flat)

API REST qui simule le **système de gestion interne d'un SFD** (institution de microfinance) : **clients** et leur dossier KYC, **comptes** et **transactions**.
Un système tiers comme IMF SHIELD vient y **lire les données** avec un jeton en lecture seule, à son rythme, ou **reçoit ses événements** par webhook signé.

</div>

## 🎖️ Fonctionnalités

- **Dossier client complet** : identité, activité professionnelle, bénéficiaires effectifs, documents, auto-déclarations PPE et sanctions, pour une personne physique comme pour une personne morale.
- **Comptes et opérations** : ouverture de comptes, dépôts, retraits et virements avec contrôle du solde, comptes bloqués qui refusent toute opération.
- **Listes fermées** : agences, professions, tranches de revenus, sources des fonds et motifs de retrait exposés avec leur code et leur libellé ; tout code inconnu est refusé.
- **Synchronisation incrémentale** : les listes de clients, de comptes et de transactions se filtrent sur `modifie_depuis` et se trient par date de modification, pour qu'un consommateur ne relise que ce qui a changé.
- **Connexions de systèmes tiers** : un jeton en lecture seule, limité aux données choisies, et un abonnement webhook, créés en une seule requête et révocables.
- **Webhooks sortants** : onze événements métier envoyés en arrière-plan, signés en HMAC-SHA256, retentés en cas d'échec et renvoyables à la main.
- **Journal des accès** : chaque requête reçue est enregistrée avec le nom du consommateur, pour suivre en direct les appels d'un système tiers.
- **Mise à niveau automatique de la base** : une base plus ancienne est complétée au démarrage, sans perte de données.

Le cahier des charges d'origine est dans [prompt-simulateur-imf-v2.md](prompt-simulateur-imf-v2.md).

## 📋 Prérequis

- **Python 3.14** (version avec laquelle la suite de tests passe).
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

# Démarrer l'API sur http://127.0.0.1:8011
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Le schéma de la base est créé au premier démarrage. La documentation interactive est servie sur http://127.0.0.1:8011/docs.

## ⚙️ Utilisation

### 🚀 Démarrer le serveur

```bash
# Depuis la racine du dépôt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Dans l'espace de travail IMF SHIELD, le dépôt est cloné dans `simulateur/backend`, à côté de l'interface du simulateur (`simulateur/frontend`), dont le `Makefile` prépare un environnement partagé `simulateur/.venv-backend` et démarre l'API sur `127.0.0.1:8011` :

```bash
# Depuis simulateur/frontend : créer l'environnement, puis démarrer l'API
make backend-install
make backend
```

`GET /` répond sans jeton et renvoie l'adresse de la documentation.

### 🔑 Authentification

Toutes les routes `/api/v1/…` exigent l'en-tête `Authorization: Bearer <jeton>`. Deux sortes de jetons sont acceptées :

- **`SIMULATEUR_API_TOKEN`**, le jeton d'administration : il a tous les droits ; c'est celui de l'interface du simulateur.
- **Le jeton d'une connexion** (voir « Connexions de systèmes tiers ») : en lecture seule, il ne passe que les requêtes `GET` et seulement sur les données cochées pour sa connexion (`403` sinon) ; il est refusé (`401`) une fois la connexion révoquée.

Un en-tête absent, mal formé ou portant un jeton inconnu reçoit `401`.

```bash
# Lire les listes fermées avec le jeton d'administration du fichier .env
JETON=$(grep '^SIMULATEUR_API_TOKEN=' .env | cut -d= -f2-)
curl -H "Authorization: Bearer $JETON" http://127.0.0.1:8011/api/v1/referentiels
```

Toutes les listes paginées acceptent `limite` et `decalage`, et renvoient l'enveloppe `{ total, limite, decalage, resultats }`. Celles des clients, des comptes et des transactions sont triées par `updated_at` croissant et filtrables par `modifie_depuis` : un consommateur mémorise la date de la dernière ligne lue et repart de là.

### 👥 Clients

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/v1/clients` | liste, filtrable par `type`, `agence`, `nationalite`, `modifie_depuis`, et `recherche` |
| `GET` | `/api/v1/clients/{external_id}` | dossier complet, comptes compris |
| `POST` | `/api/v1/clients` | création, avec ouverture automatique d'un premier compte |
| `PUT` | `/api/v1/clients/{external_id}` | modification **partielle** : seuls les champs fournis changent |
| `POST` | `/api/v1/clients/{external_id}/documents` | ajout d'un document |
| `PUT` · `DELETE` | `/api/v1/clients/{external_id}/documents/{document_id}` | modification ou suppression d'un document |
| `POST` | `/api/v1/clients/{external_id}/beneficiaires-effectifs` | ajout d'un bénéficiaire effectif |
| `PUT` · `DELETE` | `/api/v1/clients/{external_id}/beneficiaires-effectifs/{beneficiaire_id}` | modification ou suppression d'un bénéficiaire effectif |

**Identification selon le type.** Une personne physique (`type: physique`) s'identifie par sa `piece_identite` (`{ type, numero }`), obligatoire. Une personne morale (`type: morale`) s'identifie par son `numero_rccm` et son `numero_cuce`, tous deux obligatoires ; elle n'a pas de pièce d'identité, ce sont ses bénéficiaires effectifs qui portent chacun la leur (`type_piece_identite`, `numero_piece_identite`). Une combinaison incohérente est refusée en `422`, y compris après une modification partielle.

**Bénéficiaires effectifs.** Une personne morale doit en déclarer au moins un (`422` sinon) ; le dernier ne peut pas être supprimé (`409`).

**Unicité.** Deux clients actifs ne peuvent pas partager la même pièce d'identité (type et numéro), ni le même RCCM, ni le même CUCE : le conflit est renvoyé en `409`.

**Recherche.** `recherche` effectue une recherche partielle, insensible à la casse, sur l'identifiant du client (`CL-EXT-0010` ou `0010`), le nom, les prénoms et le numéro d'identifiant légal (pièce d'identité, RCCM ou CUCE). Elle se combine avec les autres filtres et la pagination.

**Contenu du dossier.**

- `agence` et `activite_professionnelle.profession` n'acceptent que des codes des listes fermées ; `activite_professionnelle.tranche_revenus_mensuels` aussi. Les champs `revenus_mensuels_min` et `revenus_mensuels_max` sont refusés en saisie (`422`) et renvoyés en lecture avec les bornes de la tranche.
- `activite_professionnelle.autres_activites` (liste de `{ secteur_activite, description }`) complète l'activité principale ; elle est remplacée en bloc lors d'un `PUT`.
- `auto_declaration_ppe` (`{ est_ppe_ou_proche, precisions }`) et `auto_declaration_sanctions` (`{ est_sous_sanctions, precisions }`) sont des données déclaratives : le client dit s'il est une personne politiquement exposée ou visé par une mesure de sanction ; ce système ne vérifie rien.
- Champs facultatifs de situation familiale : `situation_matrimoniale` (`celibataire`, `marie`, `divorce`, `veuf`, `union_libre`), `nom_conjoint`, `nom_pere`, `profession_pere`, `nom_mere`, `profession_mere`.
- `coordonnees_gps` (`{ latitude, longitude }`), facultatif.
- `statut` vaut `actif` (par défaut) ou `cloture`.
- `compte_initial` (`{ type_compte, devise, solde_initial, date_deblocage }`), facultatif en création, paramètre le compte ouvert automatiquement ; les champs omis reprennent les valeurs par défaut de la configuration.

Ajouter, modifier ou supprimer un document ou un bénéficiaire effectif met à jour le `updated_at` du client : la synchronisation par `modifie_depuis` voit donc les évolutions du dossier KYC.

```bash
# Créer une personne physique ; son premier compte est ouvert en même temps
curl -X POST http://127.0.0.1:8011/api/v1/clients \
  -H "Authorization: Bearer $JETON" -H "Content-Type: application/json" \
  -d '{"type": "physique", "nom": "Mensah", "prenoms": "Afi", "nationalite": "TG",
       "piece_identite": {"type": "CNI", "numero": "TG-0012345"},
       "adresse": "Lomé, Bè", "telephone": "+228 90 00 00 00", "agence": "lome_centre",
       "activite_professionnelle": {"profession": "commercant", "tranche_revenus_mensuels": "de_1_a_200000"}}'
```

### 💳 Comptes et transactions

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/v1/comptes` | liste, filtrable par `client_external_id` et `modifie_depuis` |
| `GET` | `/api/v1/comptes/{external_id}` | détail |
| `POST` | `/api/v1/clients/{client_external_id}/comptes` | ouverture d'un compte supplémentaire |
| `GET` | `/api/v1/transactions` | liste, filtrable par `client_external_id`, `compte_external_id`, `type_operation`, `date_debut`, `date_fin` et `modifie_depuis` |
| `GET` | `/api/v1/transactions/{external_id}` | détail |
| `POST` | `/api/v1/comptes/{compte_external_id}/transactions` | dépôt, retrait ou virement |

**Numéro de compte.** Il est généré sous la forme `{PREFIXE_NUMERO_COMPTE}-{id sur 6 chiffres}`, par exemple `CPT-000123`. Le type de compte vaut `courant`, `epargne` ou `bloque`.

**Comptes bloqués.** Un compte de type `bloque` refuse **toute** opération, en entrée comme en sortie (dépôt, retrait, virement émis ou reçu), avec un refus `400`. Sa `date_deblocage`, facultative, fixe la fin du blocage ; sans date, il est bloqué sans limite. `est_bloque` indique en lecture si le compte refuse les opérations aujourd'hui. `date_deblocage` est refusée (`422`) pour un autre type de compte.

**Source des fonds et motif.** Un dépôt exige `source_fonds`, un retrait exige `motif_retrait`, tous deux pris dans les listes fermées ; un virement n'accepte ni l'un ni l'autre (`422` sinon). `precision_motif`, facultatif, précise la réponse, par exemple pour « autre ».

**Mécanique comptable.**

- Un dépôt crédite le compte.
- Un retrait le débite ; il est refusé (`400`) si le solde est insuffisant.
- Un virement débite le compte source (refusé si le solde est insuffisant) et crédite `compte_destination_external_id` s'il est fourni ; sans destination, il est traité comme un virement sortant vers un tiers externe. Le compte de destination doit exister (`404`) et différer du compte source (`400`).

Les filtres `client_external_id` et `compte_external_id` retiennent une transaction dont le compte est la source **ou** la destination : un virement reçu figure dans l'historique du bénéficiaire. `client_destination_external_id` identifie directement le client crédité.

```bash
# Déposer 50 000 XOF sur un compte, en déclarant l'origine des fonds
curl -X POST http://127.0.0.1:8011/api/v1/comptes/CPT-EXT-0001/transactions \
  -H "Authorization: Bearer $JETON" -H "Content-Type: application/json" \
  -d '{"type_operation": "depot", "montant": 50000, "source_fonds": "activite_commerciale"}'
```

### 📚 Listes fermées

`GET /api/v1/referentiels` renvoie les listes fermées du système, chaque valeur avec le **code** à envoyer et le **libellé** à afficher :

| Liste | Utilisée par |
|---|---|
| `agences` | `agence` du client (`lome_centre`, `kara`…) |
| `categories_profession` et `professions` | `activite_professionnelle.profession` (`etudiant`, `commercant`…) ; `sans_employeur` marque les professions de la catégorie `sans_activite` |
| `tranches_revenus_mensuels` | `activite_professionnelle.tranche_revenus_mensuels`, avec les bornes en XOF |
| `sources_fonds` | `source_fonds` d'un dépôt |
| `motifs_retrait` | `motif_retrait` d'un retrait |
| `types_compte` | `type_compte` : `courant`, `epargne`, `bloque` |

Un code inconnu est refusé en `422`. Les agences et les professions vivent en base (tables `agences`, `categories_profession` et `professions`) : les valeurs initiales sont insérées au démarrage si elles manquent, et une ligne ajoutée à la main est aussitôt acceptée et listée. Les autres listes sont définies dans `app/referentiels.py`.

### 🔗 Connexions de systèmes tiers

Un système tiers (par exemple IMF SHIELD, via sa passerelle d'intégration) a besoin de **recevoir les événements**, de **lire des données** à la demande, ou des deux. Une connexion regroupe ces accès :

- un abonnement webhook vers `url_reception`, avec son secret de signature (absent si `url_reception` n'est pas fourni) ;
- un jeton API dédié, en **lecture seule**, limité aux données cochées dans `acces` (absent si la liste est vide).

Il en faut au moins un des deux (`422` sinon). Le jeton et le secret ne sont renvoyés **qu'une fois**, à leur création. Ils restent valables tant que la connexion n'est pas révoquée ; perdus, on révoque la connexion et on en crée une nouvelle.

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/api/v1/connexions` | crée la connexion et renvoie ses accès |
| `GET` | `/api/v1/connexions`, `/api/v1/connexions/{external_id}` | liste et détail, sans aucun secret |
| `PUT` | `/api/v1/connexions/{external_id}` | change le nom, l'adresse, les événements ou les accès |
| `POST` | `/api/v1/connexions/{external_id}/revoquer` | désactive le jeton et l'abonnement, définitivement |

Ces routes sont réservées au jeton d'administration (`403` avec le jeton d'une connexion). Le test et les livraisons du webhook d'une connexion passent par `/api/v1/webhooks/{abonnement_id}`.

**Périmètre du jeton (`acces`).**

| Code | Routes lisibles |
|---|---|
| `clients` | `/api/v1/clients…` (documents et bénéficiaires effectifs compris) |
| `comptes` | `/api/v1/comptes…` |
| `transactions` | `/api/v1/transactions…` |
| `referentiels` | `/api/v1/referentiels` |
| `journal` | `/api/v1/journal-acces` |
| `webhooks` | `/api/v1/webhooks/evenements`, et l'abonnement de la connexion avec ses livraisons |

Une route hors des accès cochés renvoie `403`, comme toute requête `POST`, `PUT` ou `DELETE` : le système tiers ne modifie rien.

**Création.**

```json
{
  "nom": "IMF Shield",
  "url_reception": "http://localhost:5678/webhook/sfd/v1/events",
  "evenements": [],
  "acces": ["clients", "comptes", "transactions", "referentiels"]
}
```

Réponse (`201`) :

```json
{
  "connexion_id": "CNX-EXT-0001",
  "api": { "url_base": "http://127.0.0.1:8011/api/v1", "jeton": "<jeton>", "portee": "lecture", "acces": ["clients", "comptes", "transactions", "referentiels"] },
  "webhook": { "abonnement_id": "WH-EXT-0001", "url_reception": "http://localhost:5678/webhook/sfd/v1/events", "secret": "<secret>", "evenements": [] }
}
```

`url_base` reprend `URL_PUBLIQUE_API`.

**Modification.** `PUT /api/v1/connexions/{external_id}` garde le jeton et le secret existants :

- changer `acces` ou `evenements` s'applique immédiatement ;
- `url_reception: null` coupe le webhook ; une nouvelle adresse le réactive, avec le même secret ;
- ajouter des accès à une connexion sans jeton, ou une adresse à une connexion sans webhook, les crée : leurs secrets sont renvoyés une fois dans `nouveaux_acces`, au même format qu'à la création.

Une connexion révoquée ne se modifie plus (`409`).

**Sécurité.**

- Le jeton (`secrets.token_urlsafe(32)`) n'est stocké que sous forme d'empreinte SHA-256, avec ses 8 premiers caractères pour l'affichage (table `consommateurs_api`).
- Le secret du webhook reste stocké tel quel, comme pour tout abonnement : une signature HMAC ne se calcule pas à partir d'une empreinte.
- Le journal des accès nomme la connexion (« IMF Shield (CNX-EXT-0001) »), et la connexion indique la dernière utilisation de son jeton.
- L'abonnement d'une connexion ne peut être ni supprimé seul, ni réactivé après la révocation (`409`).

### 📨 Webhooks sortants

Un système tiers peut s'abonner aux événements du simulateur au lieu de venir les lire.

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/v1/webhooks/evenements` | liste des événements disponibles |
| `GET` · `POST` | `/api/v1/webhooks` | liste des abonnements, création d'un abonnement |
| `GET` · `PUT` · `DELETE` | `/api/v1/webhooks/{external_id}` | détail, modification, suppression |
| `POST` | `/api/v1/webhooks/{external_id}/test` | envoi d'un événement `ping` |
| `GET` | `/api/v1/webhooks/{external_id}/livraisons` | historique des livraisons |
| `POST` | `/api/v1/webhooks/livraisons/{livraison_id}/renvoyer` | nouvel envoi d'une livraison |

Un abonnement porte `url`, `evenements`, `description` et `actif`. Le `secret` de signature (16 caractères au moins) est généré s'il n'est pas fourni, et n'est renvoyé **qu'à la création**.

**Événements.** `client.cree`, `client.modifie`, `compte.cree`, `compte.modifie` (solde modifié par une transaction), `transaction.creee`, `document.ajoute`, `document.modifie`, `document.supprime`, `beneficiaire.ajoute`, `beneficiaire.modifie`, `beneficiaire.supprime`. Une liste `evenements` vide abonne à tous.

**Envoi.** Chaque livraison est un `POST` JSON `{ id, evenement, date, donnees }`, où `donnees` reprend la ressource au format de lecture de l'API. Elle part en arrière-plan, après la réponse à l'appelant : un abonné lent ou injoignable ne ralentit pas l'API. En-têtes :

- `X-Simulateur-Signature` : `sha256=` suivi du HMAC-SHA256 du corps avec le secret de l'abonnement ; l'abonné le recalcule pour vérifier l'origine ;
- `X-Simulateur-Evenement` : le nom de l'événement ;
- `X-Simulateur-Livraison` : l'identifiant de la livraison.

Une réponse 2xx vaut succès. Sinon, l'envoi est retenté jusqu'à `WEBHOOK_TENTATIVES_MAX` fois, avec un délai croissant à partir de `WEBHOOK_DELAI_ENTRE_TENTATIVES_SECONDES`, puis la livraison est marquée `echouee` ; elle peut être renvoyée à la main.

### 👁️ Journal des accès

`GET /api/v1/journal-acces` liste les requêtes reçues par l'API (méthode, chemin, code de réponse, consommateur), des plus récentes aux plus anciennes, avec `limite` et `decalage`. Les pages de documentation (`/docs`, `/redoc`, `/openapi.json`) n'y figurent pas.

### 🗄️ Base de données

Le simulateur fonctionne sur PostgreSQL. Dans l'espace de travail IMF SHIELD, le serveur tourne dans Docker, partagé avec le backend d'IMF SHIELD :

```bash
# Depuis IMF_SHIELD/infra/postgres
docker compose up -d
```

Dans le `.env` du simulateur :

```
DATABASE_URL=postgresql+psycopg://simulateur:<mot de passe>@localhost:5434/simulateur_imf
```

Les formes `postgresql://` et `postgres://` sont acceptées et ramenées au pilote psycopg 3. Un mot de passe contenant des caractères spéciaux doit être encodé pour l'URL (`%40` pour `@`, par exemple). Une URL `sqlite:///…` fonctionne aussi, pour un essai sans serveur.

**Mise à niveau automatique.** Le schéma est créé au démarrage, et une base plus ancienne est mise à niveau sans perte de données : les colonnes manquantes sont ajoutées, celles qu'un champ retiré du modèle a laissées sont supprimées ; sous PostgreSQL, un `ALTER TABLE` lève une contrainte `NOT NULL`, pose une valeur par défaut ou ajoute une clé étrangère ; sous SQLite, qui ne sait pas le faire, la table est reconstruite. Les anciennes valeurs sont ramenées aux listes fermées : professions reconnues par leur libellé (formes féminines comprises, « autre » sinon), tranche déduite des anciens montants, anciens types de compte ramenés à la liste, noms d'agence remplacés par leur code (un nom inconnu devient une nouvelle agence). Rien n'est à recréer à la main après un `git pull` ; `app/migrations.py` ne remplace pas Alembic.

**Charge.** Au-delà de `REQUETES_SIMULTANEES_MAX` requêtes en cours, les suivantes attendent leur tour au lieu d'épuiser le pool de connexions (voir `app/middleware.py`).

**Reprise d'une base SQLite.** `scripts/sqlite_vers_postgres.py` recopie toutes les tables d'une base SQLite du simulateur vers PostgreSQL, en conservant les identifiants internes et externes, puis recale les séquences sur `max(id) + 1` et vérifie le nombre de lignes table par table. La copie tient en une transaction : en cas d'erreur, la cible reste intacte.

```bash
# Copier une base SQLite vers PostgreSQL
.venv/bin/python scripts/sqlite_vers_postgres.py \
    --source sqlite:///../simulateur_imf.db \
    --cible "postgresql://simulateur:<mot de passe>@localhost:5434/simulateur_imf"
```

Sans argument, la source vient de `SOURCE_DATABASE_URL`, sinon du fichier `simulateur_imf.db` du dossier parent, et la cible de `CIBLE_DATABASE_URL`, puis de `DATABASE_URL`. Le script refuse d'écrire dans une base dont une table contient déjà des lignes (un simulateur démarré dessus y a par exemple inséré les listes fermées) ; `--remplacer` vide d'abord ces tables. La base SQLite source n'est pas modifiée.

### 🧪 Tests

```bash
# Lancer la suite de tests
.venv/bin/pytest
```

Les tests tournent sur la base PostgreSQL `simulateur_imf_test`, dont toutes les tables sont supprimées puis recréées au début de chaque session. Son URL vient de `TEST_DATABASE_URL` ; à défaut, elle est déduite de `DATABASE_URL` (environnement ou `.env`) en remplaçant le nom de la base. Par sécurité, seule une base dont le nom finit par `_test` est vidée.

```bash
# Désigner explicitement la base de test
TEST_DATABASE_URL="postgresql://simulateur:<mot de passe>@localhost:5434/simulateur_imf_test" .venv/bin/pytest
```

Les tests de mise à niveau d'une base SQLite (`tests/test_migrations.py`) travaillent sur des fichiers SQLite temporaires ; ceux de la mise à niveau sous PostgreSQL, dans un schéma dédié de la base de test. Les envois de webhooks passent par un transport factice.

### ⚙️ Variables d'environnement

Elles sont lues dans l'environnement ou dans `.env` ; `.env.example` sert de modèle.

| Variable | Rôle | Défaut |
|---|---|---|
| `SIMULATEUR_API_TOKEN` | Jeton d'administration de l'API | `change-moi-en-production` |
| `DATABASE_URL` | URL SQLAlchemy de la base | `sqlite:///./simulateur_imf.db` |
| `DATABASE_POOL_SIZE` | Taille du pool de connexions (PostgreSQL) | `20` |
| `DATABASE_MAX_OVERFLOW` | Connexions au-delà du pool | `30` |
| `DATABASE_POOL_TIMEOUT_SECONDES` | Attente maximale d'une connexion du pool | `10` |
| `REQUETES_SIMULTANEES_MAX` | Requêtes traitées en même temps | `15` |
| `TYPE_COMPTE_PAR_DEFAUT` | Type du compte ouvert automatiquement (`courant`, `epargne`, `bloque`) | `courant` |
| `DEVISE_PAR_DEFAUT` | Devise par défaut des comptes | `XOF` |
| `SOLDE_INITIAL_PAR_DEFAUT` | Solde initial des comptes | `0` |
| `PREFIXE_NUMERO_COMPTE` | Préfixe du numéro de compte généré | `CPT` |
| `URL_PUBLIQUE_API` | Adresse de l'API renvoyée à un système tiers connecté | `http://127.0.0.1:8011/api/v1` |
| `WEBHOOK_TIMEOUT_SECONDES` | Délai maximal d'un envoi de webhook | `5` |
| `WEBHOOK_TENTATIVES_MAX` | Tentatives avant d'abandonner un envoi | `3` |
| `WEBHOOK_DELAI_ENTRE_TENTATIVES_SECONDES` | Délai de base entre deux tentatives | `2` |

### 🗂️ Structure du projet

```
app/
  main.py           # point d'entrée FastAPI, montage des routeurs
  config.py         # configuration (variables d'environnement)
  database.py       # moteur SQLAlchemy, session
  models.py         # modèles SQLAlchemy
  schemas.py        # schémas Pydantic (entrée et sortie de l'API)
  referentiels.py   # listes fermées et leurs valeurs initiales
  security.py       # jetons d'administration et de connexion, périmètre d'accès
  middleware.py     # journal des accès, plafond de requêtes simultanées
  migrations.py     # mise à niveau d'une base plus ancienne
  webhooks.py       # émission, signature et nouvelles tentatives des webhooks
  utils.py          # identifiants, pagination
  crud/             # logique métier par ressource
  routers/          # routes FastAPI par ressource
scripts/
  sqlite_vers_postgres.py  # copie d'une base SQLite vers PostgreSQL
tests/              # tests d'API, de connexions, de webhooks et de migration
```

## 🤝 Contribuer

Les tickets et les demandes de fusion sont les bienvenus sur le dépôt [Kaleb0001/simulateur-backend](https://github.com/Kaleb0001/simulateur-backend), propriétaire de ce code. Avant d'en proposer une, vérifiez que la suite de tests passe.

## 📜 Licence

Aucune licence n'est publiée : le dépôt ne contient pas de fichier `LICENSE`.
