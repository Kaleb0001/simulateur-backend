from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..utils import generer_external_id, maintenant_utc, paginer
from . import comptes as comptes_crud


def creer_transaction(
    db: Session, compte: models.Compte, payload: schemas.TransactionCreate
) -> models.Transaction:
    """Applique la mécanique comptable de base sur le(s) compte(s) concerné(s).

    - dépôt : augmente le solde du compte.
    - retrait : diminue le solde du compte (refusé si le solde est
      insuffisant).
    - virement : diminue le solde du compte source et, si un compte de
      destination est précisé, crédite ce dernier ; sans destination
      précisée, il est traité comme un virement sortant vers un tiers
      externe (seul le débit du compte source est appliqué).
    """
    compte_destination: models.Compte | None = None
    if payload.compte_destination_external_id is not None:
        compte_destination = db.scalar(
            select(models.Compte).where(
                models.Compte.external_id == payload.compte_destination_external_id
            )
        )
        if compte_destination is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compte de destination introuvable.",
            )
        if compte_destination.id == compte.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le compte de destination doit être différent du compte source.",
            )

    for compte_vise in (compte, compte_destination):
        if compte_vise is not None and comptes_crud.est_bloque(compte_vise):
            terme = (
                f" jusqu'au {compte_vise.date_deblocage.strftime('%d/%m/%Y')}"
                if compte_vise.date_deblocage
                else ""
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le compte {compte_vise.numero_compte} est bloqué{terme}\u00a0: aucune opération n'est possible.",
            )

    if payload.type_operation == schemas.TypeOperation.depot:
        compte.solde += payload.montant
    else:  # retrait ou virement : débit du compte source
        if compte.solde < payload.montant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solde insuffisant pour cette opération.",
            )
        compte.solde -= payload.montant
        if payload.type_operation == schemas.TypeOperation.virement and compte_destination:
            compte_destination.solde += payload.montant

    transaction = models.Transaction(
        compte_id=compte.id,
        compte_destination_id=compte_destination.id if compte_destination else None,
        type_operation=payload.type_operation.value,
        montant=payload.montant,
        devise=payload.devise or compte.devise,
        canal=payload.canal,
        source_fonds=payload.source_fonds.value if payload.source_fonds else None,
        motif_retrait=payload.motif_retrait.value if payload.motif_retrait else None,
        precision_motif=payload.precision_motif,
        date_operation=payload.date_operation or maintenant_utc(),
        external_id="",
    )
    db.add(transaction)
    db.flush()

    transaction.external_id = generer_external_id("TXN-EXT", transaction.id)
    db.flush()

    return transaction


def get_transaction_by_external_id(db: Session, external_id: str) -> models.Transaction | None:
    return db.scalar(
        select(models.Transaction).where(models.Transaction.external_id == external_id)
    )


def lister_transactions(
    db: Session,
    limite: int,
    decalage: int,
    client_external_id: str | None = None,
    compte_external_id: str | None = None,
    type_operation: schemas.TypeOperation | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    modifie_depuis: datetime | None = None,
) -> tuple[int, list[models.Transaction]]:
    """`client_external_id`/`compte_external_id` filtrent sur les transactions
    où le compte visé est débité OU crédité (compte source ou destination
    d'un virement) : un virement reçu doit apparaître dans l'historique du
    client qui l'a reçu, pas seulement dans celui de l'émetteur.
    """
    stmt = select(models.Transaction)

    if client_external_id is not None or compte_external_id is not None:
        comptes_vises = select(models.Compte.id)
        if client_external_id is not None:
            comptes_vises = comptes_vises.join(models.Client).where(
                models.Client.external_id == client_external_id
            )
        if compte_external_id is not None:
            comptes_vises = comptes_vises.where(
                models.Compte.external_id == compte_external_id
            )
        stmt = stmt.where(
            or_(
                models.Transaction.compte_id.in_(comptes_vises),
                models.Transaction.compte_destination_id.in_(comptes_vises),
            )
        )

    if type_operation is not None:
        stmt = stmt.where(models.Transaction.type_operation == type_operation.value)
    if date_debut is not None:
        stmt = stmt.where(models.Transaction.date_operation >= date_debut)
    if date_fin is not None:
        stmt = stmt.where(models.Transaction.date_operation <= date_fin)
    if modifie_depuis is not None:
        stmt = stmt.where(models.Transaction.updated_at >= modifie_depuis)

    stmt = stmt.order_by(models.Transaction.updated_at.asc())

    return paginer(db, stmt, limite, decalage)


def to_read(transaction: models.Transaction) -> schemas.TransactionRead:
    return schemas.TransactionRead(
        external_id=transaction.external_id,
        compte_external_id=transaction.compte.external_id,
        client_external_id=transaction.compte.client.external_id,
        compte_destination_external_id=(
            transaction.compte_destination.external_id
            if transaction.compte_destination
            else None
        ),
        client_destination_external_id=(
            transaction.compte_destination.client.external_id
            if transaction.compte_destination
            else None
        ),
        type_operation=schemas.TypeOperation(transaction.type_operation),
        montant=transaction.montant,
        devise=transaction.devise,
        canal=transaction.canal,
        source_fonds=transaction.source_fonds,
        motif_retrait=transaction.motif_retrait,
        precision_motif=transaction.precision_motif,
        date_operation=transaction.date_operation,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )
