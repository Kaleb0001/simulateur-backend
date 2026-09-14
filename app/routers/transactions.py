from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import schemas
from ..crud import comptes as comptes_crud
from ..crud import transactions as transactions_crud
from ..database import get_db
from ..security import get_current_consumer
from ..webhooks import emettre

# Pas de prefix commun : /api/v1/transactions (liste, détail) et
# /api/v1/comptes/{...}/transactions (création) ne partagent pas de racine.
router = APIRouter(tags=["Transactions"], dependencies=[Depends(get_current_consumer)])


@router.get("/api/v1/transactions", response_model=schemas.TransactionsListResponse)
def lister_transactions(
    limite: int = Query(default=20, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
    client_external_id: str | None = None,
    compte_external_id: str | None = None,
    type_operation: schemas.TypeOperation | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    modifie_depuis: datetime | None = None,
    db: Session = Depends(get_db),
) -> schemas.TransactionsListResponse:
    total, resultats = transactions_crud.lister_transactions(
        db,
        limite,
        decalage,
        client_external_id=client_external_id,
        compte_external_id=compte_external_id,
        type_operation=type_operation,
        date_debut=date_debut,
        date_fin=date_fin,
        modifie_depuis=modifie_depuis,
    )
    return schemas.TransactionsListResponse(
        total=total,
        limite=limite,
        decalage=decalage,
        resultats=[transactions_crud.to_read(t) for t in resultats],
    )


@router.get("/api/v1/transactions/{external_id}", response_model=schemas.TransactionRead)
def obtenir_transaction(external_id: str, db: Session = Depends(get_db)) -> schemas.TransactionRead:
    transaction = transactions_crud.get_transaction_by_external_id(db, external_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable."
        )
    return transactions_crud.to_read(transaction)


@router.post(
    "/api/v1/comptes/{compte_external_id}/transactions",
    response_model=schemas.TransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_transaction(
    compte_external_id: str,
    payload: schemas.TransactionCreate,
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.TransactionRead:
    compte = comptes_crud.get_compte_by_external_id(db, compte_external_id)
    if compte is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")
    transaction = transactions_crud.creer_transaction(db, compte, payload)
    db.commit()
    db.refresh(transaction)
    lecture = transactions_crud.to_read(transaction)
    emettre(db, taches, schemas.EvenementWebhook.transaction_creee, lecture.model_dump(mode="json"))
    # Le solde a bougé : chaque compte touché est aussi annoncé.
    for compte_touche in (transaction.compte, transaction.compte_destination):
        if compte_touche is not None:
            db.refresh(compte_touche)
            emettre(db, taches, schemas.EvenementWebhook.compte_modifie, comptes_crud.to_read(compte_touche).model_dump(mode="json"))
    return lecture
