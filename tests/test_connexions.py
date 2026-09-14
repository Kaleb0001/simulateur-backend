"""Connexion d'un système tiers : un abonnement webhook et un jeton API en
lecture seule limité aux données choisies, valables jusqu'à la révocation."""

import hashlib
import hmac

import httpx
import pytest

from app import models, webhooks
from app.database import SessionLocal
from tests.conftest import HEADERS
from tests.test_api import CLIENT_PAYLOAD

URL = "http://localhost:5678/webhook/sfd/v1/events"
TOUS_LES_ACCES = ["clients", "comptes", "transactions", "referentiels", "journal", "webhooks"]
CONNEXION = {"nom": "IMF Shield", "url_reception": URL, "evenements": [], "acces": TOUS_LES_ACCES}


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
def connecter(client):
    creees = []

    def _connecter(**corps):
        reponse = client.post("/api/v1/connexions", json=CONNEXION | corps, headers=HEADERS)
        assert reponse.status_code == 201, reponse.text
        creees.append(reponse.json())
        return reponse.json()

    yield _connecter
    for cree in creees:
        client.post(f"/api/v1/connexions/{cree['connexion_id']}/revoquer", headers=HEADERS)


@pytest.fixture
def connexion(connecter):
    return connecter()


def _jeton(cree):
    return {"Authorization": f"Bearer {cree['api']['jeton']}"}


def test_creation_renvoie_le_format_attendu(connexion):
    assert connexion["connexion_id"].startswith("CNX-EXT-")
    assert connexion["api"]["url_base"] == "http://127.0.0.1:8011/api/v1"
    assert connexion["api"]["portee"] == "lecture"
    assert connexion["api"]["acces"] == TOUS_LES_ACCES
    assert len(connexion["api"]["jeton"]) >= 40
    webhook = connexion["webhook"]
    assert webhook["abonnement_id"].startswith("WH-EXT-")
    assert webhook["url_reception"] == URL
    assert webhook["evenements"] == []
    assert len(webhook["secret"]) >= 40


def test_une_connexion_sans_webhook_ni_acces_est_refusee(client):
    reponse = client.post("/api/v1/connexions", json={"nom": "Vide", "acces": []}, headers=HEADERS)
    assert reponse.status_code == 422


def test_webhook_seul_ou_jeton_seul(connecter):
    webhook_seul = connecter(acces=[])
    assert webhook_seul["api"] is None and webhook_seul["webhook"] is not None
    jeton_seul = connecter(url_reception=None, acces=["referentiels"])
    assert jeton_seul["webhook"] is None and jeton_seul["api"] is not None


def test_aucun_secret_en_lecture_ni_en_base(client, connexion):
    detail = client.get(f"/api/v1/connexions/{connexion['connexion_id']}", headers=HEADERS)
    liste = client.get("/api/v1/connexions", headers=HEADERS)
    for texte in (detail.text, liste.text):
        assert connexion["api"]["jeton"] not in texte
        assert connexion["webhook"]["secret"] not in texte
    lecture = detail.json()
    assert lecture["consommateur"]["prefixe_jeton"] == connexion["api"]["jeton"][:8]
    assert lecture["webhook"]["url_reception"] == URL
    assert lecture["acces"] == TOUS_LES_ACCES

    with SessionLocal() as db:
        consommateur = db.query(models.ConsommateurApi).filter_by(prefixe_jeton=connexion["api"]["jeton"][:8]).one()
        assert consommateur.empreinte_jeton == hashlib.sha256(connexion["api"]["jeton"].encode()).hexdigest()


def test_le_jeton_lit_ce_qui_est_coche_et_ne_modifie_rien(client, connexion):
    jeton = _jeton(connexion)
    abonnement = connexion["webhook"]["abonnement_id"]
    for chemin in ("/api/v1/clients", "/api/v1/comptes", "/api/v1/transactions", "/api/v1/referentiels",
                   "/api/v1/journal-acces", f"/api/v1/webhooks/{abonnement}", f"/api/v1/webhooks/{abonnement}/livraisons"):
        assert client.get(chemin, headers=jeton).status_code == 200, chemin

    assert client.post("/api/v1/clients", json=CLIENT_PAYLOAD, headers=jeton).status_code == 403
    assert client.put("/api/v1/clients/CL-EXT-0001", json={"nom": "X"}, headers=jeton).status_code == 403
    assert client.delete(f"/api/v1/webhooks/{abonnement}", headers=jeton).status_code == 403


def test_le_jeton_ne_lit_pas_ce_qui_n_est_pas_coche(client, connecter):
    cree = connecter(acces=["referentiels"])
    jeton = _jeton(cree)
    assert client.get("/api/v1/referentiels", headers=jeton).status_code == 200
    for chemin in ("/api/v1/clients", "/api/v1/comptes", "/api/v1/transactions", "/api/v1/journal-acces",
                   f"/api/v1/webhooks/{cree['webhook']['abonnement_id']}"):
        assert client.get(chemin, headers=jeton).status_code == 403, chemin


def test_le_jeton_ne_voit_que_son_propre_abonnement(client, connecter):
    premiere, seconde = connecter(), connecter()
    jeton = _jeton(premiere)
    assert client.get("/api/v1/webhooks", headers=jeton).status_code == 403
    assert client.get(f"/api/v1/webhooks/{seconde['webhook']['abonnement_id']}", headers=jeton).status_code == 403


def test_le_jeton_ne_gere_pas_les_connexions(client, connexion):
    assert client.get("/api/v1/connexions", headers=_jeton(connexion)).status_code == 403


def test_modifier_les_acces_garde_le_jeton(client, connexion):
    jeton = _jeton(connexion)
    chemin = f"/api/v1/connexions/{connexion['connexion_id']}"
    reponse = client.put(chemin, json={"acces": ["referentiels"], "evenements": ["client.cree"]}, headers=HEADERS)
    assert reponse.status_code == 200
    assert reponse.json()["nouveaux_acces"] is None
    assert reponse.json()["webhook"]["evenements"] == ["client.cree"]
    assert client.get("/api/v1/referentiels", headers=jeton).status_code == 200
    assert client.get("/api/v1/clients", headers=jeton).status_code == 403


def test_ajouter_un_jeton_ou_un_webhook_renvoie_ses_secrets(client, connecter):
    webhook_seul = connecter(acces=[])
    chemin = f"/api/v1/connexions/{webhook_seul['connexion_id']}"
    ajout = client.put(chemin, json={"acces": ["clients"]}, headers=HEADERS).json()
    assert ajout["nouveaux_acces"]["api"]["jeton"]
    assert client.get("/api/v1/clients", headers=_jeton(ajout["nouveaux_acces"])).status_code == 200

    jeton_seul = connecter(url_reception=None, acces=["clients"])
    chemin = f"/api/v1/connexions/{jeton_seul['connexion_id']}"
    ajout = client.put(chemin, json={"url_reception": URL}, headers=HEADERS).json()
    assert ajout["nouveaux_acces"]["webhook"]["secret"]
    assert ajout["webhook"]["actif"] is True


def test_couper_le_webhook_et_retirer_tous_les_acces_est_refuse(client, connexion):
    chemin = f"/api/v1/connexions/{connexion['connexion_id']}"
    assert client.put(chemin, json={"url_reception": None, "acces": []}, headers=HEADERS).status_code == 422
    coupe = client.put(chemin, json={"url_reception": None}, headers=HEADERS).json()
    assert coupe["webhook"]["actif"] is False


def test_le_journal_nomme_la_connexion_et_la_derniere_utilisation(client, connexion):
    client.get("/api/v1/referentiels", headers=_jeton(connexion))
    journal = client.get("/api/v1/journal-acces", params={"limite": 200}, headers=HEADERS).json()
    assert f"IMF Shield ({connexion['connexion_id']})" in {e["consommateur"] for e in journal["resultats"]}
    detail = client.get(f"/api/v1/connexions/{connexion['connexion_id']}", headers=HEADERS).json()
    assert detail["consommateur"]["derniere_utilisation"] is not None


def test_revocation_invalide_le_jeton_et_l_abonnement(client, connexion):
    jeton = _jeton(connexion)
    chemin = f"/api/v1/connexions/{connexion['connexion_id']}"
    reponse = client.post(f"{chemin}/revoquer", headers=HEADERS)
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "revoquee"

    assert client.get("/api/v1/clients", headers=jeton).status_code == 401
    abonnement = connexion["webhook"]["abonnement_id"]
    assert client.get(f"/api/v1/webhooks/{abonnement}", headers=HEADERS).json()["actif"] is False
    assert client.put(f"/api/v1/webhooks/{abonnement}", json={"actif": True}, headers=HEADERS).status_code == 409
    assert client.put(chemin, json={"acces": ["clients"]}, headers=HEADERS).status_code == 409


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

    envois = [r for r in abonne if str(r.url) == URL]
    assert envois
    secret = connexion["webhook"]["secret"].encode()
    for requete in envois:
        attendue = "sha256=" + hmac.new(secret, requete.content, hashlib.sha256).hexdigest()
        assert requete.headers["X-Simulateur-Signature"] == attendue
