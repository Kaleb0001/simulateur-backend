"""Envoi des événements de ce système à ses abonnés (webhooks sortants).

Chaque écriture de l'API (client, compte, transaction, document, bénéficiaire)
émet un événement. Pour chaque abonnement actif qui le suit, une livraison est
enregistrée puis envoyée en arrière-plan, après la réponse à l'appelant : un
abonné lent ou injoignable ne ralentit jamais l'API.

Format d'un envoi (POST, JSON) :

    {"id": "LIV-...", "evenement": "client.cree", "date": "2026-09-14T09:12:00Z",
     "donnees": { ...la ressource, au format de lecture de l'API... }}

En-têtes : X-Simulateur-Evenement, X-Simulateur-Livraison et
X-Simulateur-Signature, qui vaut « sha256=<HMAC-SHA256 du corps avec le secret
de l'abonnement> ». L'abonné recalcule la signature pour vérifier l'origine.

Une réponse 2xx vaut succès. Sinon la livraison est retentée jusqu'à
WEBHOOK_TENTATIVES_MAX fois, avec un délai croissant, puis marquée « echouee » ;
elle peut être renvoyée à la main.
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import timezone

import httpx
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .config import get_settings
from .database import SessionLocal
from .utils import maintenant_utc

logger = logging.getLogger(__name__)

# Remplacé par un transport factice dans les tests.
transport: httpx.BaseTransport | None = None


def signer(secret: str, corps: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()


def _abonnes(db: Session, evenement: str) -> list[models.WebhookAbonnement]:
    abonnements = db.scalars(
        select(models.WebhookAbonnement).where(models.WebhookAbonnement.actif.is_(True))
    ).all()
    retenus = []
    for abonnement in abonnements:
        suivis = json.loads(abonnement.evenements or "[]")
        if not suivis or evenement in suivis:
            retenus.append(abonnement)
    return retenus


def preparer_livraison(
    db: Session, abonnement: models.WebhookAbonnement, evenement: str, donnees: dict
) -> models.WebhookLivraison:
    identifiant = f"LIV-{uuid.uuid4().hex[:12].upper()}"
    charge = {
        "id": identifiant,
        "evenement": evenement,
        "date": maintenant_utc().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "donnees": donnees,
    }
    livraison = models.WebhookLivraison(
        external_id=identifiant,
        abonnement_id=abonnement.id,
        evenement=evenement,
        charge_utile=json.dumps(charge, ensure_ascii=False, default=str),
    )
    db.add(livraison)
    return livraison


def emettre(
    db: Session, taches: BackgroundTasks, evenement: schemas.EvenementWebhook, donnees: dict
) -> None:
    """Enregistre une livraison par abonné concerné et planifie leur envoi.

    `donnees` doit déjà être sérialisable en JSON (model_dump(mode="json")).
    """
    abonnes = _abonnes(db, evenement.value)
    if not abonnes:
        return
    livraisons = [preparer_livraison(db, a, evenement.value, donnees) for a in abonnes]
    db.commit()
    for livraison in livraisons:
        taches.add_task(livrer, livraison.external_id)


def livrer(livraison_external_id: str) -> None:
    """Envoie une livraison, avec relances. Ouvre sa propre session : la tâche
    s'exécute après la fin de la requête qui l'a planifiée.
    """
    settings = get_settings()
    db = SessionLocal()
    try:
        livraison = db.scalar(
            select(models.WebhookLivraison).where(
                models.WebhookLivraison.external_id == livraison_external_id
            )
        )
        if livraison is None:
            return
        abonnement = livraison.abonnement
        corps = livraison.charge_utile.encode()
        entetes = {
            "Content-Type": "application/json",
            "User-Agent": "simulateur-imf-webhooks/1.0",
            "X-Simulateur-Evenement": livraison.evenement,
            "X-Simulateur-Livraison": livraison.external_id,
            "X-Simulateur-Signature": signer(abonnement.secret, corps),
        }

        for tentative in range(1, settings.webhook_tentatives_max + 1):
            livraison.tentatives += 1
            try:
                with httpx.Client(timeout=settings.webhook_timeout_secondes, transport=transport) as http:
                    reponse = http.post(abonnement.url, content=corps, headers=entetes)
                livraison.dernier_code_http = reponse.status_code
                livraison.derniere_reponse = reponse.text[:1000]
                livraison.derniere_erreur = None
                if 200 <= reponse.status_code < 300:
                    livraison.statut = "reussie"
                    livraison.livree_le = maintenant_utc()
                    db.commit()
                    return
            except httpx.HTTPError as erreur:
                livraison.dernier_code_http = None
                livraison.derniere_reponse = None
                livraison.derniere_erreur = str(erreur)[:500]
            livraison.statut = "echouee" if tentative == settings.webhook_tentatives_max else "en_attente"
            db.commit()
            if tentative < settings.webhook_tentatives_max:
                time.sleep(settings.webhook_delai_entre_tentatives_secondes * tentative)
    except Exception:  # noqa: BLE001 - une tâche d'arrière-plan ne doit pas mourir en silence
        logger.exception("Échec inattendu de la livraison %s", livraison_external_id)
    finally:
        db.close()


def to_read(abonnement: models.WebhookAbonnement) -> schemas.WebhookAbonnementRead:
    return schemas.WebhookAbonnementRead(
        external_id=abonnement.external_id,
        url=abonnement.url,
        description=abonnement.description,
        evenements=json.loads(abonnement.evenements or "[]"),
        actif=abonnement.actif,
        created_at=abonnement.created_at,
        updated_at=abonnement.updated_at,
    )


def livraison_to_read(livraison: models.WebhookLivraison) -> schemas.WebhookLivraisonRead:
    return schemas.WebhookLivraisonRead(
        external_id=livraison.external_id,
        abonnement_external_id=livraison.abonnement.external_id,
        evenement=livraison.evenement,
        statut=livraison.statut,
        tentatives=livraison.tentatives,
        dernier_code_http=livraison.dernier_code_http,
        derniere_reponse=livraison.derniere_reponse,
        derniere_erreur=livraison.derniere_erreur,
        charge_utile=json.loads(livraison.charge_utile),
        created_at=livraison.created_at,
        livree_le=livraison.livree_le,
    )
