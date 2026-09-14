from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import schemas
from ..config import Settings, get_settings
from ..crud import clients as clients_crud
from ..database import get_db
from ..models import Client
from ..security import get_current_consumer

router = APIRouter(
    prefix="/api/v1/clients",
    tags=["Clients"],
    dependencies=[Depends(get_current_consumer)],
)


def _obtenir_client_ou_404(db: Session, external_id: str) -> Client:
    client = clients_crud.get_client_by_external_id(db, external_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")
    return client


@router.get("", response_model=schemas.ClientsListResponse)
def lister_clients(
    limite: int = Query(default=20, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
    type: schemas.TypeClient | None = None,
    agence: str | None = None,
    modifie_depuis: datetime | None = None,
    recherche: str | None = Query(
        default=None,
        description=(
            "Recherche partielle, insensible à la casse, sur le nom, les "
            "prénoms ou le numéro d'identifiant légal (pièce d'identité, "
            "RCCM ou CUCE)."
        ),
    ),
    db: Session = Depends(get_db),
) -> schemas.ClientsListResponse:
    total, resultats = clients_crud.lister_clients(
        db,
        limite,
        decalage,
        type=type,
        agence=agence,
        modifie_depuis=modifie_depuis,
        recherche=recherche,
    )
    return schemas.ClientsListResponse(
        total=total,
        limite=limite,
        decalage=decalage,
        resultats=[clients_crud.to_summary(c) for c in resultats],
    )


@router.get("/{external_id}", response_model=schemas.ClientRead)
def obtenir_client(external_id: str, db: Session = Depends(get_db)) -> schemas.ClientRead:
    client = _obtenir_client_ou_404(db, external_id)
    return clients_crud.to_read(client)


@router.post("", response_model=schemas.ClientRead, status_code=status.HTTP_201_CREATED)
def creer_client(
    payload: schemas.ClientCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.ClientRead:
    client = clients_crud.creer_client(db, payload, settings)
    return clients_crud.to_read(client)


@router.put("/{external_id}", response_model=schemas.ClientRead)
def modifier_client(
    external_id: str, payload: schemas.ClientUpdate, db: Session = Depends(get_db)
) -> schemas.ClientRead:
    client = _obtenir_client_ou_404(db, external_id)
    client = clients_crud.mettre_a_jour_client(db, client, payload)
    return clients_crud.to_read(client)


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


@router.post(
    "/{external_id}/documents",
    response_model=schemas.DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def ajouter_document(
    external_id: str, payload: schemas.DocumentCreate, db: Session = Depends(get_db)
) -> schemas.DocumentRead:
    client = _obtenir_client_ou_404(db, external_id)
    document = clients_crud.ajouter_document(db, client, payload)
    return schemas.DocumentRead.model_validate(document)


@router.put("/{external_id}/documents/{document_id}", response_model=schemas.DocumentRead)
def modifier_document(
    external_id: str,
    document_id: str,
    payload: schemas.DocumentUpdate,
    db: Session = Depends(get_db),
) -> schemas.DocumentRead:
    client = _obtenir_client_ou_404(db, external_id)
    document = clients_crud.get_document(db, client, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    document = clients_crud.mettre_a_jour_document(db, document, payload)
    return schemas.DocumentRead.model_validate(document)


@router.delete("/{external_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_document(external_id: str, document_id: str, db: Session = Depends(get_db)) -> None:
    client = _obtenir_client_ou_404(db, external_id)
    document = clients_crud.get_document(db, client, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    clients_crud.supprimer_document(db, document)


# --------------------------------------------------------------------------
# Bénéficiaires effectifs
# --------------------------------------------------------------------------


@router.post(
    "/{external_id}/beneficiaires-effectifs",
    response_model=schemas.BeneficiaireEffectifRead,
    status_code=status.HTTP_201_CREATED,
)
def ajouter_beneficiaire(
    external_id: str,
    payload: schemas.BeneficiaireEffectifCreate,
    db: Session = Depends(get_db),
) -> schemas.BeneficiaireEffectifRead:
    client = _obtenir_client_ou_404(db, external_id)
    beneficiaire = clients_crud.ajouter_beneficiaire(db, client, payload)
    return schemas.BeneficiaireEffectifRead.model_validate(beneficiaire)


@router.put(
    "/{external_id}/beneficiaires-effectifs/{beneficiaire_id}",
    response_model=schemas.BeneficiaireEffectifRead,
)
def modifier_beneficiaire(
    external_id: str,
    beneficiaire_id: str,
    payload: schemas.BeneficiaireEffectifUpdate,
    db: Session = Depends(get_db),
) -> schemas.BeneficiaireEffectifRead:
    client = _obtenir_client_ou_404(db, external_id)
    beneficiaire = clients_crud.get_beneficiaire(db, client, beneficiaire_id)
    if beneficiaire is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bénéficiaire effectif introuvable."
        )
    beneficiaire = clients_crud.mettre_a_jour_beneficiaire(db, beneficiaire, payload)
    return schemas.BeneficiaireEffectifRead.model_validate(beneficiaire)


@router.delete(
    "/{external_id}/beneficiaires-effectifs/{beneficiaire_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_beneficiaire(
    external_id: str, beneficiaire_id: str, db: Session = Depends(get_db)
) -> None:
    client = _obtenir_client_ou_404(db, external_id)
    beneficiaire = clients_crud.get_beneficiaire(db, client, beneficiaire_id)
    if beneficiaire is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bénéficiaire effectif introuvable."
        )
    clients_crud.supprimer_beneficiaire(db, beneficiaire)
