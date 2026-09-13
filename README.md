# Simulateur de système de gestion interne d'IMF

API backend (FastAPI + SQLite) simulant l'outil de gestion interne d'une
Institution de Microfinance : clients (dossier KYC), comptes et
transactions. Ce système est **indépendant de Vigie** : il n'appelle jamais
aucun système tiers, il se contente d'exposer des données via une API REST
protégée par clé API. C'est à un consommateur externe (Vigie) d'interroger
cette API, au rythme qui lui convient, avec un mécanisme de synchronisation
incrémentale (`modifie_depuis`).

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
| `TYPE_COMPTE_PAR_DEFAUT` | Type du compte auto-créé | `Courant` |
| `DEVISE_PAR_DEFAUT` | Devise par défaut des comptes | `XOF` |
| `SOLDE_INITIAL_PAR_DEFAUT` | Solde initial des comptes | `0` |
| `PREFIXE_NUMERO_COMPTE` | Préfixe du numéro de compte auto-généré | `CPT` |
| `DATABASE_URL` | URL SQLAlchemy | `sqlite:///./simulateur_imf.db` |

## Endpoints

### Clients
- `GET /api/v1/clients` — liste paginée (`limite`, `decalage`), filtrable (`type`, `agence`, `modifie_depuis`)
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
  middleware.py      # journal des accès
  utils.py          # génération d'identifiants, pagination
  crud/             # logique métier par ressource
  routers/          # endpoints FastAPI par ressource
tests/              # tests d'API (pytest + TestClient)
```
