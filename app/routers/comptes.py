from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import schemas
from ..config import Settings, get_settings
from ..crud import clients as clients_crud
from ..crud import comptes as comptes_crud
from ..database import get_db
from ..security import get_current_consumer

# Pas de prefix commun : cette ressource est exposée à la fois sous
# /api/v1/comptes (liste, détail) et sous /api/v1/clients/{...}/comptes
# (création d'un compte additionnel pour un client existant).
router = APIRouter(tags=["Comptes"], dependencies=[Depends(get_current_consumer)])


@router.get("/api/v1/comptes", response_model=schemas.ComptesListResponse)
def lister_comptes(
    limite: int = Query(default=20, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
    client_external_id: str | None = None,
    modifie_depuis: datetime | None = None,
    db: Session = Depends(get_db),
) -> schemas.ComptesListResponse:
    total, resultats = comptes_crud.lister_comptes(
        db, limite, decalage, client_external_id=client_external_id, modifie_depuis=modifie_depuis
    )
    return schemas.ComptesListResponse(
        total=total,
        limite=limite,
        decalage=decalage,
        resultats=[comptes_crud.to_read(c) for c in resultats],
    )


@router.get("/api/v1/comptes/{external_id}", response_model=schemas.CompteRead)
def obtenir_compte(external_id: str, db: Session = Depends(get_db)) -> schemas.CompteRead:
    compte = comptes_crud.get_compte_by_external_id(db, external_id)
    if compte is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable.")
    return comptes_crud.to_read(compte)


@router.post(
    "/api/v1/clients/{client_external_id}/comptes",
    response_model=schemas.CompteRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_compte_additionnel(
    client_external_id: str,
    payload: schemas.CompteCreate | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.CompteRead:
    client = clients_crud.get_client_by_external_id(db, client_external_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")
    compte = comptes_crud.creer_compte(db, client, settings, payload or schemas.CompteCreate())
    db.commit()
    db.refresh(compte)
    return comptes_crud.to_read(compte)
