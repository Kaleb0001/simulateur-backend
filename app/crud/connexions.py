"""Connexion d'un système tiers : un abonnement webhook et un jeton API en
lecture seule, créés ensemble et révoqués ensemble."""

import json
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings
from ..security import empreinte_jeton
from ..utils import generer_external_id, maintenant_utc, paginer


def creer_connexion(
    db: Session, payload: schemas.ConnexionCreate, settings: Settings
) -> schemas.ConnexionCreee:
    evenements = [e.value for e in payload.evenements]
    secret = secrets.token_urlsafe(32)
    jeton = secrets.token_urlsafe(32)

    abonnement = models.WebhookAbonnement(
        external_id="_tmp_connexion",
        url=str(payload.url_reception),
        description=payload.nom,
        evenements=json.dumps(evenements),
        secret=secret,
        actif=True,
    )
    consommateur = models.ConsommateurApi(
        external_id="_tmp_connexion",
        nom=payload.nom,
        empreinte_jeton=empreinte_jeton(jeton),
        prefixe_jeton=jeton[:8],
        portee=schemas.PorteeJeton.lecture.value,
        actif=True,
    )
    db.add_all([abonnement, consommateur])
    db.flush()
    abonnement.external_id = generer_external_id("WH-EXT", abonnement.id)
    consommateur.external_id = generer_external_id("API-EXT", consommateur.id)

    connexion = models.Connexion(
        external_id="_tmp_connexion",
        nom=payload.nom,
        url_reception=str(payload.url_reception),
        evenements=json.dumps(evenements),
        abonnement_id=abonnement.id,
        consommateur_id=consommateur.id,
        statut=schemas.StatutConnexion.active.value,
    )
    db.add(connexion)
    db.flush()
    connexion.external_id = generer_external_id("CNX-EXT", connexion.id)
    # Le journal des accès montre le nom et l'identifiant de la connexion.
    consommateur.nom = f"{payload.nom} ({connexion.external_id})"
    db.commit()

    return schemas.ConnexionCreee(
        connexion_id=connexion.external_id,
        api=schemas.AccesApi(
            url_base=settings.url_publique_api.rstrip("/"),
            jeton=jeton,
            portee=schemas.PorteeJeton.lecture,
        ),
        webhook=schemas.AccesWebhook(
            abonnement_id=abonnement.external_id,
            url_reception=abonnement.url,
            secret=secret,
            evenements=evenements,
        ),
    )


def lister_connexions(db: Session, limite: int, decalage: int) -> tuple[int, list[models.Connexion]]:
    stmt = select(models.Connexion).order_by(models.Connexion.id.desc())
    return paginer(db, stmt, limite, decalage)


def obtenir_connexion(db: Session, external_id: str) -> models.Connexion:
    connexion = db.scalar(select(models.Connexion).where(models.Connexion.external_id == external_id))
    if connexion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connexion introuvable.")
    return connexion


def revoquer_connexion(db: Session, connexion: models.Connexion) -> models.Connexion:
    """Désactive le jeton et l'abonnement. Définitif : pour reconnecter le
    système, on crée une nouvelle connexion."""
    if connexion.statut != schemas.StatutConnexion.revoquee.value:
        connexion.statut = schemas.StatutConnexion.revoquee.value
        connexion.revoquee_le = maintenant_utc()
        connexion.consommateur.actif = False
        connexion.abonnement.actif = False
        db.commit()
        db.refresh(connexion)
    return connexion


def connexion_de_l_abonnement(db: Session, abonnement: models.WebhookAbonnement) -> models.Connexion | None:
    return db.scalar(select(models.Connexion).where(models.Connexion.abonnement_id == abonnement.id))


def to_read(connexion: models.Connexion) -> schemas.ConnexionRead:
    consommateur = connexion.consommateur
    return schemas.ConnexionRead(
        external_id=connexion.external_id,
        nom=connexion.nom,
        url_reception=connexion.url_reception,
        evenements=json.loads(connexion.evenements or "[]"),
        statut=schemas.StatutConnexion(connexion.statut),
        abonnement_id=connexion.abonnement.external_id,
        consommateur=schemas.ConsommateurApiRead(
            external_id=consommateur.external_id,
            prefixe_jeton=consommateur.prefixe_jeton,
            portee=schemas.PorteeJeton(consommateur.portee),
            actif=consommateur.actif,
            derniere_utilisation=consommateur.derniere_utilisation,
        ),
        created_at=connexion.created_at,
        updated_at=connexion.updated_at,
        revoquee_le=connexion.revoquee_le,
    )
