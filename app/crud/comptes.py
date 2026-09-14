from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings
from ..utils import generer_external_id, generer_numero_compte, maintenant_utc, paginer


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
        type_compte=schemas.TypeCompte(type_compte).value,
        date_deblocage=payload.date_deblocage if payload else None,
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


def est_bloque(compte: models.Compte, aujourd_hui: date | None = None) -> bool:
    """Un compte bloqué refuse toute opération, en entrée comme en sortie :
    sans date de déblocage, le blocage n'a pas de terme ; avec une date, il
    cesse à cette date.
    """
    if compte.type_compte != schemas.TypeCompte.bloque.value:
        return False
    if compte.date_deblocage is None:
        return True
    return (aujourd_hui or maintenant_utc().date()) < compte.date_deblocage


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
        type_compte=schemas.TypeCompte(compte.type_compte),
        date_deblocage=compte.date_deblocage,
        est_bloque=est_bloque(compte),
        devise=compte.devise,
        solde=compte.solde,
        client_external_id=compte.client.external_id,
        created_at=compte.created_at,
        updated_at=compte.updated_at,
    )
