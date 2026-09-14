# Simulateur de système de gestion interne d'IMF

API backend (FastAPI + SQLite) simulant l'outil de gestion interne d'une
Institution de Microfinance : clients (dossier KYC), comptes et
transactions. Ce système est **indépendant de Vigie** : il expose ses données via une API REST
protégée par clé API. Un consommateur externe (Vigie) peut interroger cette
API au rythme qui lui convient, avec un mécanisme de synchronisation
incrémentale (`modifie_depuis`), ou s'abonner à ses événements par webhook
(voir « Webhooks sortants »).

Voir [prompt-simulateur-imf-v2.md](prompt-simulateur-imf-v2.md) pour le
cahier des charges complet.

## Démarrage rapide

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell : .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

L'API est servie sur http://127.0.0.1:8000, la documentation interactive
Swagger sur http://127.0.0.1:8000/docs.

Un fichier `.env` est déjà présent avec un jeton de démo
(`demo-hackathon-vigie`) — à changer avant tout usage réel. `.env.example`
liste toutes les variables disponibles.

> **Schéma de base de données.** Le schéma est créé au démarrage
> (`create_all`) et une base SQLite plus ancienne est **mise à niveau
> automatiquement**, sans perte de données : les colonnes manquantes sont
> ajoutées, et la table est reconstruite lorsque SQLite ne sait pas faire
> autrement (contrainte `NOT NULL` à lever, valeur par défaut à poser).
> Rien à supprimer ni à recréer à la main après un `git pull`. Voir
> `app/migrations.py` — ce n'est pas un remplaçant d'Alembic, juste le
> nécessaire pour qu'une base de démonstration survive à l'évolution du
> modèle pendant le hackathon.

### Changements de contrat récents (à répercuter côté frontend)

- `piece_identite` peut désormais être `null` dans les réponses : il est
  absent pour les personnes morales, qui portent `numero_rccm` et
  `numero_cuce` (voir « Identification selon le type de client »).
- `activite_professionnelle.revenus_mensuels_estimes` est remplacé par
  `revenus_mensuels_min` / `revenus_mensuels_max`.
- Nouveaux champs : `autres_activites`, `situation_matrimoniale`,
  `nom_conjoint`, `nom_pere`, `profession_pere`, `nom_mere`,
  `profession_mere`, `coordonnees_gps`, `compte_initial` (en création), et
  `client_destination_external_id` sur les transactions.

## Authentification

Toutes les routes `/api/v1/...` exigent :

```
Authorization: Bearer <SIMULATEUR_API_TOKEN>
```

Le jeton est lu depuis la variable d'environnement `SIMULATEUR_API_TOKEN`
(voir `app/config.py`). La structure (`Settings.api_keys`, un dict
jeton → nom de consommateur) permet d'ajouter facilement plusieurs
clés/consommateurs plus tard sans changer le code des routes.

## Configuration (variables d'environnement)

| Variable | Rôle | Défaut |
|---|---|---|
| `SIMULATEUR_API_TOKEN` | Jeton API attendu | `change-moi-en-production` |
| `TYPE_COMPTE_PAR_DEFAUT` | Type du compte auto-créé (`courant`, `epargne`, `bloque`) | `courant` |
| `DEVISE_PAR_DEFAUT` | Devise par défaut des comptes | `XOF` |
| `SOLDE_INITIAL_PAR_DEFAUT` | Solde initial des comptes | `0` |
| `PREFIXE_NUMERO_COMPTE` | Préfixe du numéro de compte auto-généré | `CPT` |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///./simulateur_imf.db` |
| `WEBHOOK_TIMEOUT_SECONDES` | Délai maximal d'un envoi de webhook | `5` |
| `WEBHOOK_TENTATIVES_MAX` | Tentatives avant d'abandonner un envoi | `3` |
| `WEBHOOK_DELAI_ENTRE_TENTATIVES_SECONDES` | Délai de base entre deux tentatives | `2` |

## Endpoints

### Clients
- `GET /api/v1/clients` — liste paginée (`limite`, `decalage`), filtrable (`type`, `agence`, `nationalite`, `modifie_depuis`) et recherchable (`recherche`)
- `GET /api/v1/clients/{external_id}` — dossier complet (identité, activité professionnelle, bénéficiaires effectifs, documents, comptes)
- `POST /api/v1/clients` — création (crée aussi automatiquement le premier compte du client)
- `PUT /api/v1/clients/{external_id}` — modification **partielle** (seuls les champs fournis sont modifiés)

### Documents et bénéficiaires effectifs (sous-ressources)
- `POST/PUT/DELETE /api/v1/clients/{external_id}/documents[/{document_id}]`
- `POST/PUT/DELETE /api/v1/clients/{external_id}/beneficiaires-effectifs[/{beneficiaire_id}]`

### Comptes
- `GET /api/v1/comptes` — liste, filtrable (`client_external_id`, `modifie_depuis`)
- `GET /api/v1/comptes/{external_id}` — détail
- `POST /api/v1/clients/{external_id}/comptes` — ouverture d'un compte additionnel

### Transactions
- `GET /api/v1/transactions` — liste, filtrable (`client_external_id`, `compte_external_id`, `type_operation`, `date_debut`, `date_fin`, `modifie_depuis`)
- `GET /api/v1/transactions/{external_id}` — détail
- `POST /api/v1/comptes/{external_id}/transactions` — création (dépôt / retrait / virement)

### Journal des accès
- `GET /api/v1/journal-acces` — historique des requêtes reçues par l'API (utile pendant la démo pour visualiser en direct les appels de Vigie)

Toutes les listes renvoient l'enveloppe `{ total, limite, decalage, resultats }`
et sont triées par `updated_at` croissant, pour permettre à un consommateur
de mémoriser un simple curseur (`modifie_depuis`) plutôt que de tout
re-scanner à chaque appel.

## Identification selon le type de client

Une **personne physique** s'identifie par sa pièce d'identité
(`piece_identite`, obligatoire). Une **personne morale** s'identifie par son
`numero_rccm` et son `numero_cuce` (tous deux obligatoires) : la pièce
d'identité n'a pas de sens à ce niveau, ce sont ses **bénéficiaires
effectifs** qui portent chacun la leur (`type_piece_identite` /
`numero_piece_identite` sur chaque bénéficiaire).

Les combinaisons incohérentes sont refusées en 422 : une personne physique
sans pièce d'identité ou portant un RCCM/CUCE, une personne morale sans
RCCM/CUCE ou portant une pièce d'identité. Le contrôle s'applique aussi
après une mise à jour partielle.

L'unicité entre clients **actifs** porte sur la pièce d'identité (type +
numéro) pour une personne physique, et sur le RCCM puis le CUCE (contrôlés
séparément) pour une personne morale — conflit renvoyé en 409.

## Activités multiples

Une personne morale peut exercer plusieurs activités.
`activite_professionnelle.autres_activites` est une liste de
`{ secteur_activite, description }` qui complète l'activité principale
(`secteur_activite` / `profession`). Elle est **remplacée en bloc** lors
d'un `PUT /clients/{external_id}` : ce sont de simples libellés sans cycle
de vie propre, contrairement aux documents et bénéficiaires effectifs qui
ont, eux, leurs sous-ressources dédiées.

À noter : `adresse` reste un champ unique côté backend. La distinction
« adresse » / « adresse sociale » selon le type de client est un simple
libellé à gérer côté frontend.

## Recherche de clients

`GET /api/v1/clients?recherche=...` effectue une recherche partielle,
insensible à la casse, sur l'identifiant du client (`CL-EXT-0010` ou
`0010`), le nom, les prénoms et le numéro d'identifiant
légal (pièce d'identité, RCCM ou CUCE). Elle se combine avec les autres
filtres (`type`, `agence`, `modifie_depuis`) et avec la pagination.

## Compte initial personnalisable à la création d'un client

`POST /api/v1/clients` accepte un champ optionnel `compte_initial`
(`{ type_compte, devise, solde_initial }`) pour choisir le type/la devise/le
solde du compte auto-créé ; les champs omis reprennent les valeurs par
défaut configurées via variables d'environnement. Le client garde toujours
un compte dès sa création, seul son paramétrage devient choisissable.

## Champs d'identité complémentaires (ajoutés après la v2 du prompt)

En plus du dossier décrit dans `prompt-simulateur-imf-v2.md`, le client
porte désormais :

- **Situation familiale** : `situation_matrimoniale` (`celibataire` /
  `marie` / `divorce` / `veuf` / `union_libre`), `nom_conjoint`, `nom_pere`,
  `profession_pere`, `nom_mere`, `profession_mere` — tous facultatifs,
  aucune contrainte ne lie `nom_conjoint` à `situation_matrimoniale`.
- **Coordonnées GPS** : `coordonnees_gps` (`{ latitude, longitude }`),
  facultatif.
- **Revenus mensuels estimés en plage** : `activite_professionnelle`
  expose désormais `revenus_mensuels_min` / `revenus_mensuels_max` (au
  lieu d'un montant unique `revenus_mensuels_estimes`) ; une erreur 422
  est renvoyée si le minimum dépasse le maximum.

## Décisions prises sur les points laissés ouverts dans le prompt

Le prompt listait plusieurs points « à valider ». Pour permettre un
développement sans blocage, les choix suivants ont été faits :

- **Bénéficiaire effectif** : pièce d'identité (type + numéro) et fonction
  au sein de l'entité ont été ajoutées, comme proposé.
- **Documents** : structure générique (type, numéro, dates, autorité
  émettrice, statut, référence de fichier) plutôt qu'un champ dédié par
  type de pièce.
- **Numéro de compte auto-généré** : format `{PREFIXE_NUMERO_COMPTE}-{id:06d}`
  (ex. `CPT-000123`), l'id interne séquentiel garantissant l'unicité sans
  table de compteurs dédiée. Plus simple que dériver un préfixe des
  initiales de l'agence (fragile avec les accents), au prix de s'écarter
  de l'exemple `LC-000123` du prompt.
- **Sous-ressources dédiées** pour documents et bénéficiaires effectifs :
  implémentées (POST/PUT/DELETE indépendants), en plus de `PUT
  /clients/{external_id}` qui reste disponible pour le reste du dossier.
- **Unicité de la pièce d'identité** : refusée (409) entre deux clients
  **actifs** ayant le même couple (type, numéro) de pièce d'identité
  principale — vérifiée à la création et à la modification.
- **Statut du client** : champ `statut` (`actif` / `cloture`) inclus dès
  cette itération, par défaut `actif`.
- **`PUT /clients/{external_id}`** : implémenté en mise à jour
  **partielle** (seuls les champs présents dans le corps de la requête
  sont modifiés), plutôt qu'un remplacement intégral du dossier — plus
  ergonomique pour des mises à jour ponctuelles (ex. changement de
  téléphone) sans devoir renvoyer tout le dossier.
- **Virement** : la mécanique comptable de base n'étant précisée que pour
  dépôt/retrait, un virement débite toujours le compte source (refusé si
  solde insuffisant) et, si un `compte_destination_external_id` est
  fourni, crédite ce compte de destination ; sans destination précisée,
  il est traité comme un virement sortant vers un tiers externe (débit
  seul).

## Bugs corrigés suite au retour du développeur frontend

- **`POST /api/v1/clients` avec plusieurs documents/bénéficiaires effectifs**
  (500) : chaque élément recevait `external_id=""` avant enregistrement ;
  dès le deuxième élément du même type dans la même requête, SQLAlchemy
  regroupait leurs `INSERT` dans le même flush et la contrainte d'unicité
  sur `external_id` était violée. Corrigé en donnant à chaque élément un
  identifiant temporaire distinct avant le flush, remplacé par son
  identifiant définitif juste après.
- **Modification d'une sous-ressource invisible en synchronisation
  incrémentale** : ajouter, modifier ou supprimer un document ou un
  bénéficiaire effectif ne touchait que la table enfant, sans faire remonter
  le `updated_at` du client. Un consommateur qui synchronise via
  `GET /clients?modifie_depuis=...` manquait donc les évolutions du dossier
  KYC (renouvellement de pièce, changement d'actionnariat). Corrigé : toute
  modification d'une sous-ressource met à jour la date de modification du
  client. Les comptes ne sont volontairement pas concernés : ils disposent
  de leur propre endpoint de synchronisation.
- **Virements reçus absents de l'historique du destinataire** :
  `GET /api/v1/transactions` (et son usage via `client_external_id` /
  `compte_external_id`) ne filtrait que sur le compte source. Un virement
  reçu n'apparaissait donc jamais dans l'historique du compte/client
  crédité, alors même que son solde avait bien été mis à jour — un problème
  sérieux pour un endpoint dont le rôle est la surveillance des
  transactions. Corrigé : le filtre matche désormais un compte qu'il soit
  source **ou** destination. La réponse expose aussi un nouveau champ
  `client_destination_external_id` pour identifier directement le client
  crédité sans appel supplémentaire.

## Listes fermées (référentiels)

`GET /api/v1/referentiels` renvoie les listes fermées de ce système, chacune
avec le **code** à envoyer et le **libellé** à afficher :

- `agences` : `agence` n'accepte que le code d'une agence (`lome_centre`,
  `kara`…). Les agences vivent dans la table `agences`.
- `professions` (et `categories_profession`) : `activite_professionnelle.profession`
  n'accepte qu'un de ces codes (`etudiant`, `commercant`…). Elles vivent dans
  les tables `professions` et `categories_profession` ; `sans_employeur` marque
  les professions sans employeur (catégorie `sans_activite`).

Un code d'agence ou de profession inconnu est refusé en 422. Les agences et
professions initiales sont insérées au démarrage si elles manquent ; une ligne
ajoutée à la main dans ces tables est aussitôt acceptée et listée.
- `tranches_revenus_mensuels` : `activite_professionnelle.tranche_revenus_mensuels`
  remplace la saisie de `revenus_mensuels_min` / `revenus_mensuels_max`, refusée
  en 422. Les bornes de la tranche restent données en lecture.
- `types_compte` : `courant`, `epargne`, `bloque`.
- `sources_fonds` et `motifs_retrait` : voir « Transactions ».

Une base plus ancienne est convertie au démarrage : professions reconnues par
leur libellé (formes féminines comprises, « autre » sinon), tranche déduite des
anciens montants, anciens types de compte ramenés à la liste, noms d'agence
remplacés par leur code (un nom inconnu devient une nouvelle agence).

## Auto-déclaration sanctions

`auto_declaration_sanctions` (`{ est_sous_sanctions, precisions }`) complète
l'auto-déclaration PPE : le client déclare être visé ou non par une mesure de
sanction. Donnée déclarative, non vérifiée par ce système.

## Comptes bloqués

Un compte de type `bloque` refuse **toute** opération, en entrée comme en
sortie (dépôt, retrait, virement émis ou reçu), avec un refus 400. Sa
`date_deblocage`, facultative, fixe la fin du blocage : sans date, il est bloqué
sans limite. `est_bloque` indique en lecture si le compte refuse les
opérations aujourd'hui. `date_deblocage` est refusée pour un autre type.

## Transactions : source des fonds et motif

Un dépôt exige `source_fonds`, un retrait exige `motif_retrait` (codes des
référentiels) ; un virement n'accepte ni l'un ni l'autre. `precision_motif`,
facultatif, précise la réponse, par exemple pour « autre ».

## Webhooks sortants

Un système tiers peut s'abonner aux événements de ce système au lieu de venir
les lire :

- `POST /api/v1/webhooks` : abonnement (`url`, `evenements`, `description`,
  `actif`). Le `secret` de signature est généré s'il n'est pas fourni, et n'est
  renvoyé **qu'à la création**.
- `GET /api/v1/webhooks`, `GET/PUT/DELETE /api/v1/webhooks/{id}`,
  `GET /api/v1/webhooks/evenements`.
- `POST /api/v1/webhooks/{id}/test` : envoie un événement `ping`.
- `GET /api/v1/webhooks/{id}/livraisons`,
  `POST /api/v1/webhooks/livraisons/{id}/renvoyer`.

Événements : `client.cree`, `client.modifie`, `compte.cree`, `compte.modifie`
(solde modifié par une transaction), `transaction.creee`, `document.ajoute`,
`document.modifie`, `document.supprime`, `beneficiaire.ajoute`,
`beneficiaire.modifie`, `beneficiaire.supprime`. Liste vide : tous.

Chaque envoi est un `POST` JSON `{ id, evenement, date, donnees }`, où `donnees`
reprend la ressource au format de lecture de l'API. L'en-tête
`X-Simulateur-Signature` vaut `sha256=` suivi du HMAC-SHA256 du corps avec le
secret ; `X-Simulateur-Evenement` et `X-Simulateur-Livraison` accompagnent
l'envoi. L'envoi part en arrière-plan après la réponse ; sans réponse 2xx, il
est retenté jusqu'à `WEBHOOK_TENTATIVES_MAX` fois (délai
`WEBHOOK_DELAI_ENTRE_TENTATIVES_SECONDES`, croissant), puis marqué `echouee`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Les tests couvrent : authentification, création de client avec compte
auto-créé, unicité de la pièce d'identité, CRUD des sous-ressources
(documents, bénéficiaires effectifs), ouverture de compte additionnel,
dépôt/retrait/virement (y compris solde insuffisant), filtrage
`modifie_depuis`, et le journal des accès.

## Structure du projet

```
app/
  main.py           # point d'entrée FastAPI, montage des routers
  config.py         # Settings (variables d'environnement)
  database.py       # engine SQLAlchemy, session, Base
  models.py         # modèles SQLAlchemy (Client, Compte, Transaction, ...)
  schemas.py        # schémas Pydantic (entrée/sortie API)
  security.py       # authentification par clé API
  middleware.py     # journal des accès
  migrations.py     # mise à niveau d'une base SQLite plus ancienne
  utils.py          # génération d'identifiants, pagination
  crud/             # logique métier par ressource
  routers/          # endpoints FastAPI par ressource
tests/              # tests d'API et de migration (pytest + TestClient)
```
