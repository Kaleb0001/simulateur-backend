# PROMPT — Simulateur de système de gestion interne d'IMF (hackathon "Vigie")

## Révision v2 — Backend API uniquement, architecture "pull" (sans notification vers Vigie)

*Ce prompt est conçu pour être copié tel quel dans une nouvelle conversation Claude, dédiée à ce projet séparé. Il remplace la version précédente du prompt simulateur-imf.*

> **Mise à jour** : les points laissés ouverts dans la première mouture de cette révision sont désormais tranchés. Ce prompt est prêt à être utilisé pour démarrer le développement (il reste toutefois quelques propositions complémentaires à valider, listées en fin de document).

---

## Changements par rapport à la version précédente

Cette révision intervient en cours de hackathon, suite à des clarifications sur l'architecture d'intégration. Quatre changements structurants par rapport à la V1 :

1. **Backend API uniquement pour cette itération.** Le frontend (écrans de gestion clients/comptes/transactions) sera traité dans un projet ou un prompt séparé, plus tard. Ce prompt ne couvre que l'API.
2. **Inversion du flux d'intégration : de "push" à "pull".** Ce système **n'envoie plus aucune notification à Vigie**. Il n'a plus vocation à connaître l'existence de Vigie ni à l'appeler. C'est désormais à Vigie d'interroger l'API exposée ici pour récupérer les données dont il a besoin (clients, comptes, transactions), au rythme qui lui convient. Ce système redevient un pur système de gestion interne d'IMF, qui expose ses données — exactement comme le ferait un vrai core banking. **L'ancien endpoint entrant `/webhooks/vigie/statut-conformite` est définitivement supprimé** : ce système ne reçoit plus rien de Vigie non plus.
3. **Modèle de données client enrichi**, pour se rapprocher d'un dossier KYC réel : secteur et activité professionnelle, bénéficiaires effectifs plus complets, documents, et quelques champs complémentaires proposés ci-dessous (à valider).
4. **Un compte est créé automatiquement à la création de chaque client** (voir §2 "Gestion de comptes"), en plus des comptes additionnels que l'utilisateur peut créer manuellement ensuite.

---

## Contexte

Je participe à un hackathon dont l'objectif est de construire **Vigie**, le MVP d'une plateforme intelligente de conformité LBC/FT/FP pour les Institutions de Microfinance (IMF).

Ce système — le **simulateur** — représente, de façon simplifiée mais réaliste, l'outil qu'une IMF utilise déjà au quotidien pour gérer ses clients, ses comptes et ses transactions. Il est volontairement **indépendant de Vigie** : il ne sait pas que Vigie existe, ne l'appelle jamais, et se contente d'exposer une API de gestion et de consultation, comme le ferait n'importe quel système bancaire interne vis-à-vis d'un outil de conformité tiers qui viendrait s'y brancher.

**Ce projet n'a pas vocation à être un vrai produit** : c'est un outil de démonstration pour le hackathon. Le scénario de démo devient :
1. Des clients, comptes et transactions existent (ou sont créés) dans ce système, via son API.
2. Vigie interroge périodiquement (ou à la demande) l'API de ce système pour récupérer les clients et transactions nouveaux ou modifiés.
3. Vigie traite ces données de son côté (KYC, screening, profil de risque, détection) — ce traitement et son résultat n'ont pas à transiter par ce système.

---

## Ce que le simulateur doit faire

### 1. Gestion de clients (CRUD via API)

Personne physique ou personne morale, avec un dossier nettement plus étoffé qu'en V1 :

**Données d'identité** (inchangé par rapport à la V1)
- Nom / prénoms (personne physique) ou raison sociale (personne morale)
- Type de pièce d'identité + numéro
- Date de naissance / date de création
- Nationalité (ou pays d'immatriculation pour une personne morale)
- Adresse, téléphone, email, agence

**Secteur et activité professionnelle** *(nouveau)*
- Secteur d'activité (ex : agriculture, commerce, BTP, services, fonction publique...)
- Profession / fonction
- Employeur / entreprise (nom de l'employeur, ou mention "indépendant")
- Revenus mensuels estimés (montant + devise)
- Source de revenus (salaire, activité commerciale, agriculture, transferts, pension...)
- Autres sources de revenus (le cas échéant)
- Objet de la relation d'affaires (motif de l'entrée en relation : épargne, financement d'activité, transferts, etc.)

**Bénéficiaire effectif** *(personnes morales — enrichi)*
- Nom complet
- Date de naissance
- Nationalité
- Adresse
- Pourcentage de détention / de contrôle
- *(proposition, à valider)* Pièce d'identité (type + numéro) — utile pour le screening PPE effectué par Vigie
- *(proposition, à valider)* Fonction au sein de l'entité (ex : gérant, actionnaire majoritaire)

**Documents** *(nouveau)* — un client peut avoir plusieurs documents associés (pièce d'identité, justificatif de domicile, registre de commerce, statuts, carte consulaire...) :
- Type de document
- Numéro (si applicable)
- Date de délivrance
- Date d'expiration (si applicable)
- Autorité émettrice (optionnel)
- Statut (valide / expiré / en attente de renouvellement)
- Référence de fichier (simple métadonnée — pas de stockage de fichier réel nécessaire pour la démo)

**Autres informations proposées** *(à valider)*
- Canal et date d'entrée en relation (agence, agent, en ligne + date)
- Agent traitant / conseiller (nom ou identifiant interne)
- Auto-déclaration PPE : le client déclare-t-il (ou un proche) être une Personne Politiquement Exposée ? (booléen + précisions si oui) — c'est une donnée déclarative réelle qu'un système de gestion IMF collecte à l'entrée en relation, et qui a de la valeur pour le module PPE de Vigie.

### 2. Gestion de comptes (CRUD via API)

À la création d'un client, un compte lui est **automatiquement créé** — un client n'existe jamais sans compte, comme dans un vrai système de gestion d'IMF. Il peut ensuite ouvrir manuellement d'autres comptes via l'API, comme en V1.

Valeurs par défaut du compte auto-créé, **paramétrables via variables d'environnement** (jamais codées en dur) :
- Type de compte : `Courant` (ex. `TYPE_COMPTE_PAR_DEFAUT`)
- Devise : `XOF` (ex. `DEVISE_PAR_DEFAUT`)
- Solde initial : `0` (ex. `SOLDE_INITIAL_PAR_DEFAUT`)
- Numéro de compte : généré automatiquement par ce système, puisqu'il n'est plus saisi manuellement à la création du client (voir "Points à valider" pour une proposition de format).

La réponse de `POST /api/v1/clients` inclut ce compte auto-créé, pour un usage immédiat.

### 3. Gestion de transactions (CRUD via API)
Inchangé par rapport à la V1 : type d'opération (dépôt/retrait/virement), montant, devise, canal, compte concerné, date d'opération. Règle de gestion simple (mécanique comptable de base, pas de la conformité) : un dépôt augmente le solde du compte concerné, un retrait le diminue.

### 4. API de lecture pensée pour l'exploitation par Vigie
Les mêmes endpoints de lecture (GET) serviront à la fois au futur frontend et à Vigie. Voir la section "Endpoints exposés" ci-dessous pour le détail : listes filtrables/paginables, avec un filtre `modifie_depuis` pour permettre une récupération incrémentale (Vigie ne récupère que ce qui a changé depuis sa dernière synchronisation).

### 5. Journal des accès API *(optionnel mais recommandé)*
Puisqu'il n'y a plus d'appels sortants à journaliser, ce journal change de nature : il s'agit désormais d'un historique des **requêtes reçues** (endpoint, méthode, date, éventuellement le consommateur identifié par sa clé d'API). Utile pour visualiser en direct, pendant la démo, le moment où Vigie vient interroger l'API.

### Ce qu'il ne doit PAS faire
- Aucune logique de conformité (pas de KYC, pas de scoring de risque, pas de détection) — c'est le rôle exclusif de Vigie.
- **Aucun appel sortant vers Vigie ou vers un quelconque système tiers.**
- Pas de frontend dans cette itération (juste l'API — Swagger/OpenAPI généré automatiquement par FastAPI suffit pour tester et démontrer l'API en attendant le frontend).
- Pas besoin d'authentification utilisateur poussée pour la gestion (un accès simple suffit) ; en revanche, l'**API doit être protégée** pour ses consommateurs externes (voir authentification ci-dessous), car elle expose désormais des données sensibles (revenus, bénéficiaires effectifs, documents).

---

## Endpoints exposés (proposition, à ajuster)

### Authentification
Toute requête sur l'API doit présenter un header `Authorization: Bearer <token>`. Le jeton attendu est configurable via une variable d'environnement (ex. `SIMULATEUR_API_TOKEN`), jamais codé en dur. Une seule clé partagée suffit pour la démo ; la structure du code doit toutefois permettre d'ajouter facilement plusieurs clés/consommateurs si besoin plus tard.

### Clients
- `GET /api/v1/clients` — liste résumée, paginée (`limite`, `decalage`) et filtrable (`type`, `agence`, `modifie_depuis`).
- `GET /api/v1/clients/{external_id}` — détail complet (identité, activité professionnelle, bénéficiaires effectifs, documents, comptes).
- `POST /api/v1/clients` — création (utilisé par le futur frontend, ou directement via l'API/Swagger en attendant).
- `PUT /api/v1/clients/{external_id}` — modification.

Exemple de réponse `GET /api/v1/clients/{external_id}` :
```json
{
  "external_id": "CL-EXT-0001",
  "type": "physique",
  "nom": "Kodjo",
  "prenoms": "Mensah",
  "date_naissance": "1985-03-14",
  "nationalite": "Togolaise",
  "piece_identite": { "type": "CNI", "numero": "TG-0192837" },
  "adresse": "Quartier Tokoin, Lomé",
  "telephone": "+22890123456",
  "email": "kodjo.mensah@example.com",
  "agence": "Lomé-Centre",
  "activite_professionnelle": {
    "secteur_activite": "Commerce",
    "profession": "Commerçante",
    "employeur": "Indépendante",
    "revenus_mensuels_estimes": 350000,
    "devise_revenus": "XOF",
    "source_revenus": "Activité commerciale",
    "autres_sources_revenus": null,
    "objet_relation": "Épargne et financement de stock"
  },
  "beneficiaires_effectifs": [],
  "documents": [
    {
      "type": "CNI",
      "numero": "TG-0192837",
      "date_delivrance": "2020-01-10",
      "date_expiration": "2030-01-10",
      "autorite_emettrice": "ANIC",
      "statut": "valide"
    }
  ],
  "canal_entree_relation": "agence",
  "date_entree_relation": "2024-02-01",
  "agent_traitant": "Ama Koudjo",
  "auto_declaration_ppe": { "est_ppe_ou_proche": false, "precisions": null },
  "comptes": [
    {
      "external_id": "CPT-EXT-0001",
      "numero_compte": "LC-000123",
      "type_compte": "Courant",
      "solde": 0,
      "devise": "XOF"
    }
  ],
  "created_at": "2024-02-01T09:12:00Z",
  "updated_at": "2024-02-01T09:12:00Z"
}
```
*Le premier compte (`CPT-EXT-0001`) apparaît automatiquement, créé au moment de `POST /api/v1/clients` — voir §2 "Gestion de comptes".*

### Documents et bénéficiaires effectifs *(proposition complémentaire, à valider)*
Le dossier d'un client évolue dans le temps (renouvellement de pièce, changement d'actionnariat...). Plutôt que de tout repasser par `PUT /api/v1/clients/{external_id}` à chaque fois, je propose des sous-ressources dédiées :
- `POST /api/v1/clients/{external_id}/documents` — ajouter un document
- `PUT /api/v1/clients/{external_id}/documents/{document_id}` — mettre à jour un document (ex. renouvellement)
- `DELETE /api/v1/clients/{external_id}/documents/{document_id}`
- `POST /api/v1/clients/{external_id}/beneficiaires-effectifs`
- `PUT /api/v1/clients/{external_id}/beneficiaires-effectifs/{beneficiaire_id}`
- `DELETE /api/v1/clients/{external_id}/beneficiaires-effectifs/{beneficiaire_id}`

Si tu préfères rester simple pour le hackathon, on peut aussi ne garder que `PUT /api/v1/clients/{external_id}` avec le dossier complet (documents et bénéficiaires effectifs inclus) — à trancher.

### Comptes
- `GET /api/v1/comptes` — liste, filtrable par `client_external_id`, `modifie_depuis`.
- `GET /api/v1/comptes/{external_id}` — détail.
- `POST /api/v1/clients/{external_id}/comptes` — création d'un compte **additionnel** pour un client existant (le premier compte est créé automatiquement à la création du client — voir §2).

### Transactions
- `GET /api/v1/transactions` — liste globale, paginée et filtrable (`client_external_id`, `compte_external_id`, `type_operation`, `date_debut`, `date_fin`, `modifie_depuis`). **C'est l'endpoint principal que le module de surveillance de Vigie interrogera en continu.**
- `GET /api/v1/transactions/{external_id}` — détail.
- `POST /api/v1/comptes/{external_id}/transactions` — création d'une transaction.

### Convention pour la synchronisation incrémentale
Chaque ressource porte des champs `created_at` / `updated_at`. Le filtre `modifie_depuis` (datetime ISO) renvoie les enregistrements dont `updated_at >= modifie_depuis`, triés par `updated_at` croissant — ce qui permet à Vigie de mémoriser un simple curseur (le dernier `updated_at` vu) plutôt que de tout re-scanner à chaque appel.

---

## Stack technique suggérée

Toujours pas de contrainte forte, la simplicité prime :
- **Backend** : FastAPI + SQLite (cohérent avec la stack de Vigie si utile pour réutiliser des patterns communs).
- **Pas de client HTTP sortant nécessaire** (`httpx` n'est plus requis, puisqu'il n'y a plus d'appel vers Vigie).
- Documentation interactive : profiter du `/docs` (Swagger UI) généré automatiquement par FastAPI — pratique pour démontrer l'API pendant le hackathon, y compris à Vigie/aux juges, sans attendre le frontend.

---

## Ce que j'attends de toi pour démarrer

1. Propose une structure de projet simple adaptée à une API backend uniquement (pas de templates HTML).
2. Mets en place le modèle de données enrichi : clients (identité + activité professionnelle + bénéficiaires effectifs + documents + champs complémentaires), comptes, transactions.
3. Implémente les endpoints de gestion (CRUD clients/comptes/transactions), utilisables directement via Swagger en attendant le frontend.
4. Implémente les endpoints de lecture pensés pour l'exploitation par Vigie (listes filtrables/paginées avec `modifie_depuis`, détail complet).
5. Mets en place l'authentification par clé API (`Authorization: Bearer <token>`) pour protéger l'ensemble de l'API, jeton configurable via variable d'environnement.
6. (Optionnel) Journal des accès API, pour visualiser les appels reçus pendant la démo.

N'hésite pas à me poser des questions si un point ci-dessus te semble ambigu avant de commencer.

---

## Points à valider / hypothèses prises dans ce prompt

- Pour le bénéficiaire effectif, j'ai ajouté par cohérence une pièce d'identité et une fonction au sein de l'entité, en plus des champs demandés (nom complet, date de naissance, nationalité, adresse, pourcentage de détention) — à valider ou retirer.
- Pour les documents, j'ai proposé une structure générique (type, numéro, dates, autorité émettrice, statut) plutôt qu'un champ dédié par type de pièce — à valider.
- **Format du numéro de compte auto-généré** : je n'ai pas figé de format précis (proposition libre dans l'exemple ci-dessus : agence + compteur séquentiel, ex. `LC-000123`) — à ajuster selon ta préférence, ou laisser à l'appréciation de l'implémentation.
- **Sous-ressources dédiées pour documents et bénéficiaires effectifs** (ajout/mise à jour/suppression indépendants du reste du dossier) — proposition pour refléter le fait qu'un dossier KYC évolue dans le temps ; à valider, sinon on repasse simplement par `PUT /api/v1/clients/{external_id}` avec le dossier complet à chaque fois.
- **Vérification d'unicité à la création d'un client** (ex. refuser deux clients physiques actifs avec le même couple type + numéro de pièce d'identité) — proposition de règle de gestion basique (pas de la conformité, juste de l'hygiène de données), à valider.
- **Statut du client** (actif / clôturé) — pourrait représenter le cycle de vie réel d'un dossier et intéresser Vigie à terme (savoir si un client est toujours actif avant de le traiter) ; pas indispensable pour le MVP du hackathon, à inclure maintenant ou à reporter selon ta préférence.
