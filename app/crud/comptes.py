from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings
from ..utils import generer_external_id, generer_numero_compte, paginer


def creer_compte(
    db: Session,
    client: models.Client,
    settings: Settings,
    payload: schemas.CompteCreate | None = None,
) -> models.Compte:
    """Crée un compte pour un client, en s'appuyant sur les valeurs par
    défaut paramétrées via variables d'environnement pour tout champ non
    fourni. Utilisé aussi bien pour le compte auto-créé à la création du
    client que pour l'ouverture manuelle de comptes additionnels.
    """
    type_compte = (payload.type_compte if payload else None) or settings.type_compte_par_defaut
    devise = (payload.devise if payload else None) or settings.devise_par_defaut
    solde_initial = (
        payload.solde_initial
        if payload and payload.solde_initial is not None
        else settings.solde_initial_par_defaut
    )

    compte = models.Compte(
        client_id=client.id,
        type_compte=type_compte,
        devise=devise,
        solde=solde_initial,
        external_id="",
        numero_compte="",
    )
    db.add(compte)
    db.flush()  # attribue compte.id

    compte.external_id = generer_external_id("CPT-EXT", compte.id)
    compte.numero_compte = generer_numero_compte(settings.prefixe_numero_compte, compte.id)
    db.flush()

    return compte


def get_compte_by_external_id(db: Session, external_id: str) -> models.Compte | None:
    return db.scalar(select(models.Compte).where(models.Compte.external_id == external_id))


def lister_comptes(
    db: Session,
    limite: int,
    decalage: int,
    client_external_id: str | None = None,
    modifie_depuis: datetime | None = None,
) -> tuple[int, list[models.Compte]]:
    stmt = select(models.Compte)

    if client_external_id is not None:
        stmt = stmt.join(models.Client).where(models.Client.external_id == client_external_id)
    if modifie_depuis is not None:
        stmt = stmt.where(models.Compte.updated_at >= modifie_depuis)

    stmt = stmt.order_by(models.Compte.updated_at.asc())

    return paginer(db, stmt, limite, decalage)


def to_read(compte: models.Compte) -> schemas.CompteRead:
    return schemas.CompteRead(
        external_id=compte.external_id,
        numero_compte=compte.numero_compte,
        type_compte=compte.type_compte,
        devise=compte.devise,
        solde=compte.solde,
        client_external_id=compte.client.external_id,
        created_at=compte.created_at,
        updated_at=compte.updated_at,
    )
