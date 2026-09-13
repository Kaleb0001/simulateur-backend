from tests.conftest import HEADERS

CLIENT_EXTERNAL_ID: str | None = None
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
    "agence": "Lomé-Centre",
    "situation_matrimoniale": "marie",
    "nom_conjoint": "Afiwa Mensah",
    "nom_pere": "Kwame Mensah",
    "profession_pere": "Agriculteur",
    "nom_mere": "Akossiwa Mensah",
    "profession_mere": "Commerçante",
    "coordonnees_gps": {"latitude": 6.1319, "longitude": 1.2228},
    "activite_professionnelle": {
        "secteur_activite": "Commerce",
        "profession": "Commerçante",
        "employeur": "Indépendante",
        "revenus_mensuels_min": 300000,
        "revenus_mensuels_max": 400000,
        "devise_revenus": "XOF",
        "source_revenus": "Activité commerciale",
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
    assert data["activite_professionnelle"]["revenus_mensuels_min"] == 300000
    assert data["activite_professionnelle"]["revenus_mensuels_max"] == 400000
    assert len(data["documents"]) == 1
    assert data["documents"][0]["type_document"] == "CNI"
    assert len(data["comptes"]) == 1

    compte = data["comptes"][0]
    assert compte["type_compte"] == "Courant"
    assert compte["devise"] == "XOF"
    assert compte["solde"] == 0
    assert compte["numero_compte"].startswith("CPT-")

    global CLIENT_EXTERNAL_ID, COMPTE_EXTERNAL_ID
    CLIENT_EXTERNAL_ID = data["external_id"]
    COMPTE_EXTERNAL_ID = compte["external_id"]


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
        json={"telephone": "+22899999999", "activite_professionnelle": {"profession": "Grossiste"}},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["telephone"] == "+22899999999"
    assert data["activite_professionnelle"]["profession"] == "Grossiste"
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


def test_plage_revenus_invalide_rejetee(client):
    payload = dict(CLIENT_PAYLOAD)
    payload["piece_identite"] = {"type": "CNI", "numero": "TG-AUTRE-0001"}
    payload["activite_professionnelle"] = {
        "revenus_mensuels_min": 500000,
        "revenus_mensuels_max": 100000,
    }
    response = client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert response.status_code == 422


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
        json={"type_compte": "Épargne", "devise": "XOF"},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["type_compte"] == "Épargne"
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
        json={"type_operation": "depot", "montant": 10000, "canal": "agence"},
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    assert response.json()["montant"] == 10000

    compte = client.get(f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}", headers=HEADERS).json()
    assert compte["solde"] == 10000

    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "retrait", "montant": 4000, "canal": "agence"},
        headers=HEADERS,
    )
    assert response.status_code == 201
    compte = client.get(f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}", headers=HEADERS).json()
    assert compte["solde"] == 6000


def test_transaction_retrait_solde_insuffisant(client):
    response = client.post(
        f"/api/v1/comptes/{COMPTE_EXTERNAL_ID}/transactions",
        json={"type_operation": "retrait", "montant": 999999},
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
