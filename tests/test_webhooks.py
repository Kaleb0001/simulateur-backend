"""Webhooks sortants : abonnements, envoi signé, relances, renvoi manuel.

Aucun abonné réel : le transport HTTP du service est remplacé par un faux qui
enregistre chaque requête reçue et répond ce que le test lui demande.
"""

import hashlib
import hmac
import json

import httpx
import pytest

from app import webhooks
from tests.conftest import HEADERS
from tests.test_api import CLIENT_PAYLOAD


class FauxAbonne:
    def __init__(self):
        self.requetes: list[httpx.Request] = []
        self.codes: list[int] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        code = self.codes.pop(0) if self.codes else 200
        return httpx.Response(code, text="ok")


@pytest.fixture
def abonne():
    faux = FauxAbonne()
    webhooks.transport = httpx.MockTransport(faux)
    yield faux
    webhooks.transport = None


def _abonner(client, **options):
    corps = {"url": "https://vigie.example/webhooks/simulateur", "secret": "un-secret-de-test-assez-long"} | options
    reponse = client.post("/api/v1/webhooks", json=corps, headers=HEADERS)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _desabonner(client, abonnement):
    client.delete(f"/api/v1/webhooks/{abonnement['external_id']}", headers=HEADERS)


def test_le_secret_n_est_renvoye_qu_a_la_creation(client, abonne):
    abonnement = _abonner(client, secret=None)
    assert len(abonnement["secret"]) >= 32
    lecture = client.get(f"/api/v1/webhooks/{abonnement['external_id']}", headers=HEADERS).json()
    assert "secret" not in lecture
    _desabonner(client, abonnement)


def test_creation_client_envoie_client_cree_et_compte_cree_signes(client, abonne):
    abonnement = _abonner(client, evenements=["client.cree", "compte.cree"])
    payload = dict(CLIENT_PAYLOAD) | {"piece_identite": {"type": "CNI", "numero": "TG-WEBHOOK-01"}, "documents": []}
    cree = client.post("/api/v1/clients", json=payload, headers=HEADERS).json()

    evenements = [r.headers["X-Simulateur-Evenement"] for r in abonne.requetes]
    assert evenements == ["client.cree", "compte.cree"]

    requete = abonne.requetes[0]
    attendue = "sha256=" + hmac.new(b"un-secret-de-test-assez-long", requete.content, hashlib.sha256).hexdigest()
    assert requete.headers["X-Simulateur-Signature"] == attendue
    corps = json.loads(requete.content)
    assert corps["evenement"] == "client.cree"
    assert corps["donnees"]["external_id"] == cree["external_id"]
    _desabonner(client, abonnement)


def test_un_abonne_ne_recoit_que_ses_evenements(client, abonne):
    abonnement = _abonner(client, evenements=["transaction.creee"])
    payload = dict(CLIENT_PAYLOAD) | {"piece_identite": {"type": "CNI", "numero": "TG-WEBHOOK-02"}, "documents": []}
    cree = client.post("/api/v1/clients", json=payload, headers=HEADERS).json()
    assert abonne.requetes == []

    compte = cree["comptes"][0]["external_id"]
    client.post(f"/api/v1/comptes/{compte}/transactions", json={"type_operation": "depot", "montant": 5000, "source_fonds": "salaire"}, headers=HEADERS)
    assert [r.headers["X-Simulateur-Evenement"] for r in abonne.requetes] == ["transaction.creee"]
    _desabonner(client, abonnement)


def test_un_abonnement_inactif_ne_recoit_rien(client, abonne):
    abonnement = _abonner(client, actif=False)
    payload = dict(CLIENT_PAYLOAD) | {"piece_identite": {"type": "CNI", "numero": "TG-WEBHOOK-03"}, "documents": []}
    client.post("/api/v1/clients", json=payload, headers=HEADERS)
    assert abonne.requetes == []
    _desabonner(client, abonnement)


def test_relances_puis_echec_puis_renvoi(client, abonne):
    abonnement = _abonner(client, evenements=["ping"])
    abonne.codes = [500, 500, 500]
    client.post(f"/api/v1/webhooks/{abonnement['external_id']}/test", headers=HEADERS)
    assert len(abonne.requetes) == 3

    livraisons = client.get(f"/api/v1/webhooks/{abonnement['external_id']}/livraisons", headers=HEADERS).json()
    livraison = livraisons["resultats"][0]
    assert (livraison["statut"], livraison["tentatives"], livraison["dernier_code_http"]) == ("echouee", 3, 500)

    client.post(f"/api/v1/webhooks/livraisons/{livraison['external_id']}/renvoyer", headers=HEADERS)
    apres = client.get(f"/api/v1/webhooks/{abonnement['external_id']}/livraisons", headers=HEADERS).json()["resultats"][0]
    assert apres["statut"] == "reussie"
    _desabonner(client, abonnement)


def test_evenement_inconnu_refuse(client):
    reponse = client.post(
        "/api/v1/webhooks",
        json={"url": "https://vigie.example/hook", "evenements": ["client.supprime"]},
        headers=HEADERS,
    )
    assert reponse.status_code == 422
