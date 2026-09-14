"""Connexion d'un système tiers : un abonnement webhook, un jeton API en
lecture seule limité aux données choisies, ou les deux. Ils sont créés
ensemble et révoqués ensemble."""

import json
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings
from ..security import empreinte_jeton
from ..utils import generer_external_id, maintenant_utc, paginer


def _codes(valeurs) -> list[str]:
    """Les valeurs d'une liste de choix fermés, telles qu'on les stocke."""
    return [getattr(valeur, "value", valeur) for valeur in valeurs]


def _nom_consommateur(connexion: models.Connexion) -> str:
    # Le journal des accès montre le nom et l'identifiant de la connexion.
    return f"{connexion.nom} ({connexion.external_id})"


def _ajouter_webhook(
    db: Session, connexion: models.Connexion, url: str, evenements: list[str]
) -> schemas.AccesWebhook:
    secret = secrets.token_urlsafe(32)
    abonnement = models.WebhookAbonnement(
        external_id=f"_tmp_connexion_{connexion.id}",
        url=url,
        description=connexion.nom,
        evenements=json.dumps(evenements),
        secret=secret,
        actif=True,
    )
    db.add(abonnement)
    db.flush()
    abonnement.external_id = generer_external_id("WH-EXT", abonnement.id)
    connexion.abonnement_id = abonnement.id
    connexion.abonnement = abonnement
    return schemas.AccesWebhook(
        abonnement_id=abonnement.external_id, url_reception=url, secret=secret, evenements=evenements
    )


def _ajouter_jeton(db: Session, connexion: models.Connexion, settings: Settings) -> schemas.AccesApi:
    jeton = secrets.token_urlsafe(32)
    consommateur = models.ConsommateurApi(
        external_id=f"_tmp_connexion_{connexion.id}",
        nom=_nom_consommateur(connexion),
        empreinte_jeton=empreinte_jeton(jeton),
        prefixe_jeton=jeton[:8],
        portee=schemas.PorteeJeton.lecture.value,
        actif=True,
    )
    db.add(consommateur)
    db.flush()
    consommateur.external_id = generer_external_id("API-EXT", consommateur.id)
    connexion.consommateur_id = consommateur.id
    connexion.consommateur = consommateur
    return schemas.AccesApi(
        url_base=settings.url_publique_api.rstrip("/"),
        jeton=jeton,
        portee=schemas.PorteeJeton.lecture,
        acces=json.loads(connexion.acces),
    )


def creer_connexion(
    db: Session, payload: schemas.ConnexionCreate, settings: Settings
) -> schemas.ConnexionCreee:
    connexion = models.Connexion(
        external_id="_tmp_connexion",
        nom=payload.nom,
        acces=json.dumps(_codes(payload.acces)),
        statut=schemas.StatutConnexion.active.value,
    )
    db.add(connexion)
    db.flush()
    connexion.external_id = generer_external_id("CNX-EXT", connexion.id)

    webhook = (
        _ajouter_webhook(db, connexion, str(payload.url_reception), _codes(payload.evenements))
        if payload.url_reception is not None
        else None
    )
    api = _ajouter_jeton(db, connexion, settings) if payload.acces else None
    db.commit()
    return schemas.ConnexionCreee(connexion_id=connexion.external_id, api=api, webhook=webhook)


def modifier_connexion(
    db: Session, connexion: models.Connexion, payload: schemas.ConnexionUpdate, settings: Settings
) -> schemas.ConnexionModifiee:
    if connexion.statut == schemas.StatutConnexion.revoquee.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette connexion est révoquée : créez-en une nouvelle.",
        )
    donnees = payload.model_dump(exclude_unset=True)
    webhook_cree: schemas.AccesWebhook | None = None
    api_cree: schemas.AccesApi | None = None

    if donnees.get("nom") is not None:
        connexion.nom = donnees["nom"]
        if connexion.abonnement is not None:
            connexion.abonnement.description = connexion.nom
        if connexion.consommateur is not None:
            connexion.consommateur.nom = _nom_consommateur(connexion)

    if "acces" in donnees and donnees["acces"] is not None:
        connexion.acces = json.dumps(_codes(payload.acces))

    abonnement = connexion.abonnement
    evenements = _codes(payload.evenements) if payload.evenements is not None else None
    if "url_reception" in donnees:
        if payload.url_reception is None:
            if abonnement is not None:
                abonnement.actif = False
        elif abonnement is None:
            webhook_cree = _ajouter_webhook(db, connexion, str(payload.url_reception), evenements or [])
            abonnement = connexion.abonnement
        else:
            # Même abonnement, même secret : seule l'adresse change.
            abonnement.url = str(payload.url_reception)
            abonnement.actif = True
    if evenements is not None and abonnement is not None:
        abonnement.evenements = json.dumps(evenements)

    webhook_actif = connexion.abonnement is not None and connexion.abonnement.actif
    if not webhook_actif and not json.loads(connexion.acces):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=schemas.CONNEXION_VIDE)

    if json.loads(connexion.acces) and connexion.consommateur is None:
        api_cree = _ajouter_jeton(db, connexion, settings)

    db.commit()
    db.refresh(connexion)
    lecture = to_read(connexion)
    nouveaux = (
        schemas.ConnexionCreee(connexion_id=connexion.external_id, api=api_cree, webhook=webhook_cree)
        if api_cree or webhook_cree
        else None
    )
    return schemas.ConnexionModifiee(**lecture.model_dump(), nouveaux_acces=nouveaux)


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
        if connexion.consommateur is not None:
            connexion.consommateur.actif = False
        if connexion.abonnement is not None:
            connexion.abonnement.actif = False
        db.commit()
        db.refresh(connexion)
    return connexion


def connexion_de_l_abonnement(db: Session, abonnement: models.WebhookAbonnement) -> models.Connexion | None:
    return db.scalar(select(models.Connexion).where(models.Connexion.abonnement_id == abonnement.id))


def to_read(connexion: models.Connexion) -> schemas.ConnexionRead:
    abonnement = connexion.abonnement
    consommateur = connexion.consommateur
    return schemas.ConnexionRead(
        external_id=connexion.external_id,
        nom=connexion.nom,
        statut=schemas.StatutConnexion(connexion.statut),
        acces=json.loads(connexion.acces or "[]"),
        webhook=(
            schemas.WebhookConnexionRead(
                abonnement_id=abonnement.external_id,
                url_reception=abonnement.url,
                evenements=json.loads(abonnement.evenements or "[]"),
                actif=abonnement.actif,
            )
            if abonnement is not None
            else None
        ),
        consommateur=(
            schemas.ConsommateurApiRead(
                external_id=consommateur.external_id,
                prefixe_jeton=consommateur.prefixe_jeton,
                portee=schemas.PorteeJeton(consommateur.portee),
                actif=consommateur.actif,
                derniere_utilisation=consommateur.derniere_utilisation,
            )
            if consommateur is not None
            else None
        ),
        created_at=connexion.created_at,
        updated_at=connexion.updated_at,
        revoquee_le=connexion.revoquee_le,
    )
