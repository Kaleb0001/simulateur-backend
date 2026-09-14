"""Connexion d'un système tiers : un abonnement webhook et un jeton API en
lecture seule, créés ensemble, valables jusqu'à la révocation."""

import hashlib
import hmac

import httpx
import pytest

from app import models, webhooks
from app.database import SessionLocal
from tests.conftest import HEADERS
from tests.test_api import CLIENT_PAYLOAD

CONNEXION = {"nom": "IMF Shield", "url_reception": "http://localhost:5678/webhook/sfd/v1/events", "evenements": []}


@pytest.fixture
def abonne():
    requetes: list[httpx.Request] = []

    def recevoir(requete):
        requetes.append(requete)
        return httpx.Response(200, text="ok")

    webhooks.transport = httpx.MockTransport(recevoir)
    yield requetes
    webhooks.transport = None


@pytest.fixture
def connexion(client):
    reponse = client.post("/api/v1/connexions", json=CONNEXION, headers=HEADERS)
    assert reponse.status_code == 201, reponse.text
    cree = reponse.json()
    yield cree
    client.post(f"/api/v1/connexions/{cree['connexion_id']}/revoquer", headers=HEADERS)


def _jeton(cree):
    return {"Authorization": f"Bearer {cree['api']['jeton']}"}


def test_creation_renvoie_le_format_attendu(client, connexion):
    assert connexion["connexion_id"].startswith("CNX-EXT-")
    assert connexion["api"]["url_base"] == "http://127.0.0.1:8011/api/v1"
    assert connexion["api"]["portee"] == "lecture"
    assert len(connexion["api"]["jeton"]) >= 40
    webhook = connexion["webhook"]
    assert webhook["abonnement_id"].startswith("WH-EXT-")
    assert webhook["url_reception"] == CONNEXION["url_reception"]
    assert webhook["evenements"] == []
    assert len(webhook["secret"]) >= 40


def test_aucun_secret_en_lecture_ni_en_base(client, connexion):
    detail = client.get(f"/api/v1/connexions/{connexion['connexion_id']}", headers=HEADERS)
    liste = client.get("/api/v1/connexions", headers=HEADERS)
    for texte in (detail.text, liste.text):
        assert connexion["api"]["jeton"] not in texte
        assert connexion["webhook"]["secret"] not in texte
    assert detail.json()["consommateur"]["prefixe_jeton"] == connexion["api"]["jeton"][:8]

    with SessionLocal() as db:
        consommateur = db.query(models.ConsommateurApi).filter_by(prefixe_jeton=connexion["api"]["jeton"][:8]).one()
        assert consommateur.empreinte_jeton == hashlib.sha256(connexion["api"]["jeton"].encode()).hexdigest()
        assert connexion["api"]["jeton"] not in (consommateur.empreinte_jeton, consommateur.nom)


def test_le_jeton_lit_tout_et_ne_modifie_rien(client, connexion):
    jeton = _jeton(connexion)
    for chemin in ("/api/v1/clients", "/api/v1/comptes", "/api/v1/transactions", "/api/v1/referentiels",
                   "/api/v1/journal-acces", "/api/v1/webhooks"):
        assert client.get(chemin, headers=jeton).status_code == 200, chemin

    assert client.post("/api/v1/clients", json=CLIENT_PAYLOAD, headers=jeton).status_code == 403
    assert client.put("/api/v1/clients/CL-EXT-0001", json={"nom": "X"}, headers=jeton).status_code == 403
    assert client.delete(f"/api/v1/webhooks/{connexion['webhook']['abonnement_id']}", headers=jeton).status_code == 403


def test_le_jeton_ne_gere_pas_les_connexions(client, connexion):
    jeton = _jeton(connexion)
    assert client.get("/api/v1/connexions", headers=jeton).status_code == 403


def test_le_journal_nomme_la_connexion_et_la_derniere_utilisation(client, connexion):
    client.get("/api/v1/referentiels", headers=_jeton(connexion))
    journal = client.get("/api/v1/journal-acces", params={"limite": 200}, headers=HEADERS).json()
    noms = {e["consommateur"] for e in journal["resultats"]}
    assert f"IMF Shield ({connexion['connexion_id']})" in noms
    detail = client.get(f"/api/v1/connexions/{connexion['connexion_id']}", headers=HEADERS).json()
    assert detail["consommateur"]["derniere_utilisation"] is not None


def test_revocation_invalide_le_jeton_et_l_abonnement(client, connexion):
    jeton = _jeton(connexion)
    reponse = client.post(f"/api/v1/connexions/{connexion['connexion_id']}/revoquer", headers=HEADERS)
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "revoquee"

    assert client.get("/api/v1/clients", headers=jeton).status_code == 401
    abonnement = client.get(f"/api/v1/webhooks/{connexion['webhook']['abonnement_id']}", headers=HEADERS).json()
    assert abonnement["actif"] is False
    reactivation = client.put(f"/api/v1/webhooks/{connexion['webhook']['abonnement_id']}",
                              json={"actif": True}, headers=HEADERS)
    assert reactivation.status_code == 409


def test_l_abonnement_d_une_connexion_ne_se_supprime_pas_seul(client, connexion):
    reponse = client.delete(f"/api/v1/webhooks/{connexion['webhook']['abonnement_id']}", headers=HEADERS)
    assert reponse.status_code == 409


def test_le_jeton_admin_fonctionne_comme_avant(client):
    assert client.get("/api/v1/clients", headers=HEADERS).status_code == 200
    assert client.get("/api/v1/clients", headers={"Authorization": "Bearer faux"}).status_code == 401
    assert client.get("/api/v1/clients").status_code == 401


def test_le_secret_recu_verifie_la_signature(client, connexion, abonne):
    payload = dict(CLIENT_PAYLOAD) | {"piece_identite": {"type": "CNI", "numero": "TG-CONNEXION-01"}, "documents": []}
    assert client.post("/api/v1/clients", json=payload, headers=HEADERS).status_code == 201

    envois = [r for r in abonne if str(r.url) == CONNEXION["url_reception"]]
    assert envois
    secret = connexion["webhook"]["secret"].encode()
    for requete in envois:
        attendue = "sha256=" + hmac.new(secret, requete.content, hashlib.sha256).hexdigest()
        assert requete.headers["X-Simulateur-Signature"] == attendue
