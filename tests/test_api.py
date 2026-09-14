from tests.conftest import HEADERS

CLIENT_EXTERNAL_ID: str | None = None
CLIENT_MORALE_EXTERNAL_ID: str | None = None
COMPTE_EXTERNAL_ID: str | None = None
COMPTE_EPARGNE_EXTERNAL_ID: str | None = None

CLIENT_PAYLOAD = {
    "type": "physique",
    "nom": "Kodjo",
    "prenoms": "Mensah",
    "date_naissance": "1985-03-14",
    "nationalite": "Togolaise",
    "piece_identite": {"type": "CNI", "numero": "TG-0192837"},
    "adresse": "Quartier Tokoin, Lomé",
    "telephone": "+22890123456",
    "email": "kodjo.mensah@example.com",
    "agence": "lome_centre",
    "situation_matrimoniale": "marie",
    "nom_conjoint": "Afiwa Mensah",
    "nom_pere": "Kwame Mensah",
    "profession_pere": "Agriculteur",
    "nom_mere": "Akossiwa Mensah",
    "profession_mere": "Commerçante",
    "coordonnees_gps": {"latitude": 6.1319, "longitude": 1.2228},
    "activite_professionnelle": {
        "secteur_activite": "Commerce",
        "profession": "commercant",
        "employeur": "Indépendante",
        "tranche_revenus_mensuels": "de_200001_a_500000",
        "devise_revenus": "XOF",
        "objet_relation": "Épargne et financement de stock",
    },
    "documents": [
        {
            "type_document": "CNI",
            "numero": "TG-0192837",
            "date_delivrance": "2020-01-10",
            "date_expiration": "2030-01-10",
            "autorite_emettrice": "ANIC",
            "statut": "valide",
        }
    ],
    "canal_entree_relation": "agence",
    "date_entree_relation": "2024-02-01",
    "agent_traitant": "Ama Koudjo",
    "auto_declaration_ppe": {"est_ppe_ou_proche": False},
}


MORALE_PAYLOAD = {
    "type": "morale",
    "nom": "Sogex Togo SARL",
    "date_creation_entite": "2015-06-01",
    "nationalite": "Togolaise",
    "numero_rccm": "TG-LOM-2015-B-1234",
    "numero_cuce": "CUCE-0099887",
    "adresse": "Zone portuaire, Lomé",
    "telephone": "+22822334455",
    "agence": "lome_port",
    "activite_professionnelle": {
        "secteur_activite": "Import-export",
        "autres_activites": [
            {"secteur_activite": "Transport", "description": "Location de camions"},
            {"secteur_activite": "BTP"},
        ],
        "tranche_revenus_mensuels": "de_10000001_a_15000000",
        "devise_revenus": "XOF",
        "objet_relation": "Financement d'activité",
    },
    "beneficiaires_effectifs": [
        {
            "nom_complet": "Yao Amegan",
            "pourcentage_detention": 70,
            "type_piece_identite": "CNI",
            "numero_piece_identite": "TG-777888",
            "fonction": "Gérant",
        }
    ],
}


def test_authentification_requise(client):
    response = client.get("/api/v1/clients")
    assert response.status_code == 401

    response = client.get("/api/v1/clients", headers={"Authorization": "Bearer mauvais-token"})
    assert response.status_code == 401


def test_creation_client_avec_compte_auto_cree(client):
    response = client.post("/api/v1/clients", json=CLIENT_PAYLOAD, headers=HEADERS)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["external_id"].startswith("CL-EXT-")
    assert data["nom"] == "Kodjo"
    assert data["statut"] == "actif"
    assert data["piece_identite"] == {"type": "CNI", "numero": "TG-0192837"}
    assert data["situation_matrimoniale"] == "marie"
    assert data["nom_conjoint"] == "Afiwa Mensah"
    assert data["nom_pere"] == "Kwame Mensah"
    assert data["profession_pere"] == "Agriculteur"
    assert data["nom_mere"] == "Akossiwa Mensah"
    assert data["profession_mere"] == "Commerçante"
    assert data["coordonnees_gps"] == {"latitude": 6.1319, "longitude": 1.2228}
    assert data["activite_professionnelle"]["secteur_activite"] == "Commerce"
    assert data["activite_professionnelle"]["profession"] == "commercant"
    assert data["activite_professionnelle"]["tranche_revenus_mensuels"] == "de_200001_a_500000"
    # Les bornes de la tranche sont données en lecture.
    assert data["activite_professionnelle"]["revenus_mensuels_min"] == 200001
    assert data["activite_professionnelle"]["revenus_mensuels_max"] == 500000
    assert len(data["documents"]) == 1
    assert data["documents"][0]["type_document"] == "CNI"
    assert len(data["comptes"]) == 1

    compte = data["comptes"][0]
    assert compte["type_compte"] == "courant"
    assert compte["devise"] == "XOF"
    assert compte["solde"] == 0
    assert compte["numero_compte"].startswith("CPT-")

    global CLIENT_EXTERNAL_ID, COMPTE_EXTERNAL_ID
    CLIENT_EXTERNAL_ID = data["external_id"]
    COMPTE_EXTERNAL_ID = compte["external_id"]


def test_creation_client_avec_compte_initial_personnalise(client):
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-CPT-INIT-0001"}
    payload["compte_initial"] = {"type_compte": "epargne", "devise": "USD", "solde_initial": 5000}

    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 201, response.text
    compte = response.json()["comptes"][0]
    assert compte["type_compte"] == "epargne"
    assert compte["devise"] == "USD"
    assert compte["solde"] == 5000


def test_creation_client_avec_plusieurs_documents_et_beneficiaires(client):
    """Régression : un même flush ne doit pas produire deux external_id
    identiques (vide) pour deux documents/bénéficiaires créés en une seule
    requête POST /api/v1/clients.
    """
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-MULTI-0001"}
    payload["documents"] = [
        {"type_document": "CNI", "numero": "A1"},
        {"type_document": "Justificatif de domicile", "numero": "A2"},
        {"type_document": "Carte consulaire", "numero": "A3"},
    ]
    payload["beneficiaires_effectifs"] = [
        {"nom_complet": "Ben One", "pourcentage_detention": 50},
        {"nom_complet": "Ben Two", "pourcentage_detention": 50},
    ]

    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 201, response.text
    data = response.json()

    doc_ids = [d["external_id"] for d in data["documents"]]
    ben_ids = [b["external_id"] for b in data["beneficiaires_effectifs"]]
    assert len(doc_ids) == 3 and len(set(doc_ids)) == 3
    assert len(ben_ids) == 2 and len(set(ben_ids)) == 2


def test_unicite_piece_identite(client):
    response = client.post("/api/v1/clients", json=CLIENT_PAYLOAD, headers=HEADERS)
    assert response.status_code == 409


def test_obtenir_client(client):
    response = client.get(f"/api/v1/clients/{CLIENT_EXTERNAL_ID}", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["external_id"] == CLIENT_EXTERNAL_ID


def test_client_introuvable(client):
    response = client.get("/api/v1/clients/CL-EXT-9999", headers=HEADERS)
    assert response.status_code == 404


def test_lister_clients(client):
    response = client.get("/api/v1/clients", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(c["external_id"] == CLIENT_EXTERNAL_ID for c in data["resultats"])


def test_modifier_client(client):
    response = client.put(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}",
        json={"telephone": "+22899999999", "activite_professionnelle": {"profession": "grossiste"}},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["telephone"] == "+22899999999"
    assert data["activite_professionnelle"]["profession"] == "grossiste"
    # Les autres champs de l'activité professionnelle imbriquée restent en place.
    assert data["activite_professionnelle"]["secteur_activite"] == "Commerce"


def test_modifier_coordonnees_gps(client):
    response = client.put(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}",
        json={"coordonnees_gps": {"latitude": 6.14, "longitude": 1.21}},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    assert response.json()["coordonnees_gps"] == {"latitude": 6.14, "longitude": 1.21}


def test_montants_de_revenus_libres_rejetes(client):
    """Les revenus se déclarent par tranche : des montants libres sont refusés."""
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-AUTRE-0001"}
    payload["activite_professionnelle"] = {
        "revenus_mensuels_min": 100000,
        "revenus_mensuels_max": 500000,
    }
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_profession_et_tranche_hors_liste_rejetees(client):
    for activite in ({"profession": "Vendeur de pagnes"}, {"tranche_revenus_mensuels": "300000"}):
        payload = dict(CLIENT_PAYLOAD)
        payload["piece_identite"] = {"type": "CNI", "numero": "TG-AUTRE-0002"}
        payload["activite_professionnelle"] = activite
        response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
        assert response.status_code == 422, activite


def test_documents_sous_ressource(client):
    response = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/documents",
        json={"type_document": "Justificatif de domicile", "statut": "valide"},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["external_id"]

    response = client.put(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/documents/{document_id}",
        json={"statut": "expire"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["statut"] == "expire"

    response = client.delete(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/documents/{document_id}", headers=HEADERS
    )
    assert response.status_code == 204


def test_beneficiaires_effectifs_sous_ressource(client):
    response = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/beneficiaires-effectifs",
        json={"nom_complet": "Yao Amegan", "pourcentage_detention": 60},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    beneficiaire_id = response.json()["external_id"]

    response = client.put(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/beneficiaires-effectifs/{beneficiaire_id}",
        json={"pourcentage_detention": 75},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["pourcentage_detention"] == 75

    response = client.delete(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/beneficiaires-effectifs/{beneficiaire_id}",
        headers=HEADERS,
    )
    assert response.status_code == 204


def test_creation_compte_additionnel(client):
    response = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/comptes",
        json={"type_compte": "epargne", "devise": "XOF"},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["type_compte"] == "epargne"
    assert data["client_external_id"] == CLIENT_EXTERNAL_ID

    global COMPTE_EPARGNE_EXTERNAL_ID
    COMPTE_EPARGNE_EXTERNAL_ID = data["external_id"]


def test_lister_comptes_par_client(client):
    response = client.get(
        "/api/v1/comptes", params={"client_external_id": CLIENT_EXTERNAL_ID}, headers=HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


def test_transaction_depot_et_retrait(client):
    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "depot", "montant": 10000, "canal": "agence", "source_fonds": "activite_commerciale"},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    assert response.json()["montant"] == 10000

    compte = client.get(f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}", headers=HEADERS).json()
    assert compte["solde"] == 10000

    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "retrait", "montant": 4000, "canal": "agence", "motif_retrait": "achat_marchandises"},
        headers=HEADERS,
    )
    assert response.status_code == 201
    compte = client.get(f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}", headers=HEADERS).json()
    assert compte["solde"] == 6000


def test_transaction_retrait_solde_insuffisant(client):
    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "retrait", "montant": 999999, "motif_retrait": "construction"},
        headers=HEADERS,
    )
    assert response.status_code == 400


def test_transaction_virement_entre_comptes(client):
    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={
            "type_operation": "virement",
            "montant": 1000,
            "compte_destination_external_id": COMPTE_EPARGNE_EXTERNAL_ID,
        },
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text

    source = client.get(f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}", headers=HEADERS).json()
    destination = client.get(f"/api/v1/comptes/{COMPTE_EPARGNE_EXTERNAL_ID}", headers=HEADERS).json()
    assert source["solde"] == 5000
    assert destination["solde"] == 1000


def test_lister_transactions_par_compte(client):
    response = client.get(
        "/api/v1/transactions", params={"compte_external_id": COMPTE_EXTERNAL_ID}, headers=HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # depot, retrait, virement (source)


def test_virement_recu_visible_dans_historique_destinataire(client):
    """Régression : un virement reçu doit apparaître dans l'historique du
    compte/client destinataire, pas seulement dans celui de l'émetteur.
    """
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-DEST-0001"}
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 201, response.text
    destinataire = response.json()
    destinataire_compte = destinataire["comptes"][0]["external_id"]
    destinataire_client = destinataire["external_id"]

    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={
            "type_operation": "virement",
            "montant": 500,
            "compte_destination_external_id": destinataire_compte,
        },
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    assert response.json()["client_destination_external_id"] == destinataire_client

    response = client.get(
        "/api/v1/transactions",
        params={"compte_external_id": destinataire_compte},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get(
        "/api/v1/transactions",
        params={"client_external_id": destinataire_client},
        headers=HEADERS,
    )
    assert response.json()["total"] == 1


def test_modifie_depuis_incremental(client):
    reponse_initiale = client.get("/api/v1/clients", headers=HEADERS).json()
    curseur = max(c["updated_at"] for c in reponse_initiale["resultats"])

    response = client.get(
        "/api/v1/clients", params={"modifie_depuis": curseur}, headers=HEADERS
    )
    assert response.status_code == 200
    for c in response.json()["resultats"]:
        assert c["updated_at"] >= curseur


def test_journal_acces_enregistre_les_requetes(client):
    client.get("/api/v1/clients", headers=HEADERS)
    response = client.get("/api/v1/journal-acces", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(entree["chemin"] == "/api/v1/clients" for entree in data["resultats"])


# --------------------------------------------------------------------------
# Personne morale : RCCM / CUCE, activités multiples
# --------------------------------------------------------------------------


def test_creation_client_morale_avec_rccm_et_cuce(client):
    response = client.post("/api/v1/clients", json=MORALE_PAYLOAD, headers=HEADERS)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["type"] == "morale"
    assert data["numero_rccm"] == "TG-LOM-2015-B-1234"
    assert data["numero_cuce"] == "CUCE-0099887"
    # La pièce d'identité est portée par les bénéficiaires effectifs, pas par
    # la personne morale elle-même.
    assert data["piece_identite"] is None
    assert data["beneficiaires_effectifs"][0]["numero_piece_identite"] == "TG-777888"

    autres = data["activite_professionnelle"]["autres_activites"]
    assert [a["secteur_activite"] for a in autres] == ["Transport", "BTP"]
    assert autres[0]["description"] == "Location de camions"

    global CLIENT_MORALE_EXTERNAL_ID
    CLIENT_MORALE_EXTERNAL_ID = data["external_id"]


def test_client_morale_sans_rccm_ni_cuce_refuse(client):
    payload = dict(MORALE_PAYLOAD)
    payload.pop("numero_rccm")
    payload.pop("numero_cuce")
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_client_morale_avec_piece_identite_refuse(client):
    payload = dict(MORALE_PAYLOAD)
    payload["numero_rccm"] = "TG-LOM-2015-B-9999"
    payload["numero_cuce"] = "CUCE-0000001"
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-123"}
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_client_physique_avec_rccm_refuse(client):
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-PHYS-RCCM"}
    payload["numero_rccm"] = "TG-LOM-2020-B-0001"
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_unicite_rccm(client):
    payload = dict(MORALE_PAYLOAD)
    payload["numero_cuce"] = "CUCE-AUTRE-001"  # RCCM identique, CUCE différent
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 409


def test_remplacement_autres_activites(client):
    response = client.put(
        f"/api/v1/clients/{CLIENT_MORALE_EXTERNAL_ID}",
        json={
            "activite_professionnelle": {
                "autres_activites": [{"secteur_activite": "Agriculture"}]
            }
        },
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    activite = response.json()["activite_professionnelle"]
    assert [a["secteur_activite"] for a in activite["autres_activites"]] == ["Agriculture"]
    # Le reste du bloc activité professionnelle n'est pas écrasé.
    assert activite["secteur_activite"] == "Import-export"


# --------------------------------------------------------------------------
# Recherche
# --------------------------------------------------------------------------


def test_recherche_par_nom_prenoms_et_numero_piece(client):
    par_nom = client.get(
        "/api/v1/clients", params={"recherche": "kodjo"}, headers=HEADERS
    ).json()
    assert par_nom["total"] >= 1
    assert all("Kodjo" in c["nom"] for c in par_nom["resultats"])

    par_prenoms = client.get(
        "/api/v1/clients", params={"recherche": "Mensah"}, headers=HEADERS
    ).json()
    assert par_prenoms["total"] >= 1

    par_piece = client.get(
        "/api/v1/clients", params={"recherche": "TG-0192837"}, headers=HEADERS
    ).json()
    assert par_piece["total"] == 1
    assert par_piece["resultats"][0]["external_id"] == CLIENT_EXTERNAL_ID

    par_rccm = client.get(
        "/api/v1/clients", params={"recherche": "2015-B-1234"}, headers=HEADERS
    ).json()
    assert par_rccm["total"] == 1
    assert par_rccm["resultats"][0]["external_id"] == CLIENT_MORALE_EXTERNAL_ID

    aucun = client.get(
        "/api/v1/clients", params={"recherche": "zzz-introuvable"}, headers=HEADERS
    ).json()
    assert aucun["total"] == 0


# --------------------------------------------------------------------------
# Synchronisation incrémentale
# --------------------------------------------------------------------------


def test_ajout_document_fait_remonter_updated_at_du_client(client):
    """Un consommateur qui synchronise sur `modifie_depuis` doit voir le
    dossier ressortir quand une de ses sous-ressources change.
    """
    avant = client.get(
        f"/api/v1/clients/{CLIENT_MORALE_EXTERNAL_ID}", headers=HEADERS
    ).json()["updated_at"]

    response = client.post(
        f"/api/v1/clients/{CLIENT_MORALE_EXTERNAL_ID}/documents",
        json={"type_document": "Registre de commerce", "numero": "RC-2015"},
        headers=HEADERS,
    )
    assert response.status_code == 201

    apres = client.get(
        f"/api/v1/clients/{CLIENT_MORALE_EXTERNAL_ID}", headers=HEADERS
    ).json()["updated_at"]
    assert apres > avant

    vus = client.get(
        "/api/v1/clients", params={"modifie_depuis": apres}, headers=HEADERS
    ).json()
    assert any(c["external_id"] == CLIENT_MORALE_EXTERNAL_ID for c in vus["resultats"])


# --------------------------------------------------------------------------
# Auto-déclaration sanctions, référentiels, types de compte
# --------------------------------------------------------------------------


def test_auto_declaration_sanctions(client):
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-SANCTION-01"}
    payload["documents"] = []
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["auto_declaration_sanctions"] == {"est_sous_sanctions": False, "precisions": None}

    response = client.put(
        f"/api/v1/clients/{data['external_id']}",
        json={"auto_declaration_sanctions": {"est_sous_sanctions": True, "precisions": "Gel des avoirs"}},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    assert response.json()["auto_declaration_sanctions"] == {
        "est_sous_sanctions": True,
        "precisions": "Gel des avoirs",
    }


def test_referentiels(client):
    response = client.get("/api/v1/referentiels", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    etudiant = next(p for p in data["professions"] if p["code"] == "etudiant")
    assert etudiant == {"code": "etudiant", "libelle": "Étudiant", "categorie": "sans_activite", "sans_employeur": True}
    assert [t["code"] for t in data["types_compte"]] == ["courant", "epargne", "bloque"]
    assert data["tranches_revenus_mensuels"][-1]["maximum"] is None


def test_type_de_compte_hors_liste_rejete(client):
    response = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/comptes",
        json={"type_compte": "Dépôt à terme"},
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_date_de_deblocage_reservee_au_compte_bloque(client):
    response = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/comptes",
        json={"type_compte": "epargne", "date_deblocage": "2030-01-01"},
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_compte_bloque_sans_terme_refuse_toute_operation(client):
    compte = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/comptes",
        json={"type_compte": "bloque", "solde_initial": 100000},
        headers=HEADERS,
    ).json()
    assert compte["est_bloque"] is True

    for operation in ("depot", "retrait"):
        response = client.post(
            f"/api/v1/comptes/{compte['external_id']}/transactions",
            json={"type_operation": operation, "montant": 1000, **({"source_fonds": "salaire"} if operation == "depot" else {"motif_retrait": "voyage"})},
            headers=HEADERS,
        )
        assert response.status_code == 400, operation
        assert "bloqué" in response.json()["detail"]

    # Un virement vers un compte bloqué est refusé aussi.
    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "virement", "montant": 10, "compte_destination_external_id": compte["external_id"]},
        headers=HEADERS,
    )
    assert response.status_code == 400


def test_compte_bloque_jusqu_a_une_date(client):
    futur = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/comptes",
        json={"type_compte": "bloque", "date_deblocage": "2999-01-01"},
        headers=HEADERS,
    ).json()
    assert futur["est_bloque"] is True
    refus = client.post(
        f"/api/v1/comptes/{futur['external_id']}/transactions",
        json={"type_operation": "depot", "montant": 1000, "source_fonds": "tontine"},
        headers=HEADERS,
    )
    assert refus.status_code == 400
    assert "01/01/2999" in refus.json()["detail"]

    passe = client.post(
        f"/api/v1/clients/{CLIENT_EXTERNAL_ID}/comptes",
        json={"type_compte": "bloque", "date_deblocage": "2020-01-01"},
        headers=HEADERS,
    ).json()
    assert passe["est_bloque"] is False
    depot = client.post(
        f"/api/v1/comptes/{passe['external_id']}/transactions",
        json={"type_operation": "depot", "montant": 1000, "source_fonds": "tontine"},
        headers=HEADERS,
    )
    assert depot.status_code == 201, depot.text


def test_depot_sans_source_et_retrait_sans_motif_refuses(client):
    for corps in (
        {"type_operation": "depot", "montant": 1000},
        {"type_operation": "retrait", "montant": 1000},
        {"type_operation": "depot", "montant": 1000, "source_fonds": "salaire", "motif_retrait": "voyage"},
        {"type_operation": "virement", "montant": 10, "source_fonds": "salaire"},
        {"type_operation": "depot", "montant": 1000, "source_fonds": "loterie"},
    ):
        reponse = client.post(f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions", json=corps, headers=HEADERS)
        assert reponse.status_code == 422, corps


def test_source_et_motif_restitues(client):
    depot = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "depot", "montant": 2000, "source_fonds": "autre", "precision_motif": "Gain de loterie"},
        headers=HEADERS,
    )
    assert depot.status_code == 201, depot.text
    data = depot.json()
    assert (data["source_fonds"], data["motif_retrait"], data["precision_motif"]) == ("autre", None, "Gain de loterie")


def test_personne_morale_sans_beneficiaire_refusee(client):
    payload = dict(MORALE_PAYLOAD) | {"numero_rccm": "TG-SANS-BEN", "numero_cuce": "CUCE-SANS-BEN", "beneficiaires_effectifs": []}
    reponse = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert reponse.status_code == 422
    assert "au moins un bénéficiaire effectif" in reponse.text


def test_dernier_beneficiaire_d_une_personne_morale_non_retirable(client):
    payload = dict(MORALE_PAYLOAD) | {"numero_rccm": "TG-UN-BEN", "numero_cuce": "CUCE-UN-BEN"}
    morale = client.post("/api/v1/clients", json=payload, headers=HEADERS).json()
    seul = morale["beneficiaires_effectifs"][0]["external_id"]
    reponse = client.delete(f"/api/v1/clients/{morale['external_id']}/beneficiaires-effectifs/{seul}", headers=HEADERS)
    assert reponse.status_code == 409


def test_passage_en_personne_morale_sans_beneficiaire_refuse(client):
    payload = dict(CLIENT_PAYLOAD) | {"piece_identite": {"type": "CNI", "numero": "TG-DEVIENT-MORALE"}, "documents": []}
    physique = client.post("/api/v1/clients", json=payload, headers=HEADERS).json()
    reponse = client.put(
        f"/api/v1/clients/{physique['external_id']}",
        json={"type": "morale", "piece_identite": None, "numero_rccm": "TG-DM", "numero_cuce": "CUCE-DM"},
        headers=HEADERS,
    )
    assert reponse.status_code == 422


def test_source_de_revenus_supprimee(client):
    reponse = client.get(f"/api/v1/clients/{CLIENT_EXTERNAL_ID}", headers=HEADERS)
    assert "source_revenus" not in reponse.json()["activite_professionnelle"]


def test_recherche_par_identifiant_client(client):
    for terme in (CLIENT_EXTERNAL_ID, CLIENT_EXTERNAL_ID.split("-")[-1], CLIENT_EXTERNAL_ID.lower()):
        reponse = client.get("/api/v1/clients", params={"recherche": terme, "limite": 200}, headers=HEADERS)
        assert reponse.status_code == 200
        assert CLIENT_EXTERNAL_ID in [c["external_id"] for c in reponse.json()["resultats"]], terme


def test_filtre_par_nationalite(client):
    reponse = client.get("/api/v1/clients", params={"nationalite": "Togolaise", "limite": 200}, headers=HEADERS)
    assert reponse.status_code == 200
    resultats = reponse.json()["resultats"]
    assert resultats and all(c["nationalite"] == "Togolaise" for c in resultats)
    vide = client.get("/api/v1/clients", params={"nationalite": "Islande"}, headers=HEADERS).json()
    assert vide["total"] == 0


def test_referentiels_agences_et_professions_en_base(client):
    donnees = client.get("/api/v1/referentiels", headers=HEADERS).json()
    agences = {a["code"]: a for a in donnees["agences"]}
    assert agences["kara"]["nom"] == "Kara"
    professions = {p["code"]: p for p in donnees["professions"]}
    assert professions["etudiant"]["sans_employeur"] is True
    assert professions["commercant"]["sans_employeur"] is False


def test_agence_inconnue_refusee(client):
    payload = {**CLIENT_PAYLOAD, "agence": "Lomé-Centre"}
    payload["piece_identite"] = {"type": "CNI", "numero": "AGENCE-INCONNUE-1"}
    reponse = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert reponse.status_code == 422
    assert reponse.json()["detail"][0]["loc"] == ["body", "agence"]


def test_profession_inconnue_refusee(client):
    payload = {**CLIENT_PAYLOAD, "piece_identite": {"type": "CNI", "numero": "PROF-INCONNUE-1"}}
    payload["activite_professionnelle"] = {"profession": "astronaute"}
    reponse = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert reponse.status_code == 422
    assert reponse.json()["detail"][0]["loc"] == ["body", "activite_professionnelle", "profession"]

