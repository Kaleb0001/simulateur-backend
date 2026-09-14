from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import schemas
from ..config import Settings, get_settings
from ..crud import clients as clients_crud
from ..database import get_db
from ..models import Client
from ..security import get_current_consumer
from ..webhooks import emettre
from ..crud import comptes as comptes_crud

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
    nationalite: str | None = None,
    modifie_depuis: datetime | None = None,
    recherche: str | None = Query(
        default=None,
        description=(
            "Recherche partielle, insensible à la casse, sur l'identifiant du "
            "client, le nom, les prénoms ou le numéro d'identifiant légal "
            "(pièce d'identité, RCCM ou CUCE)."
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
        nationalite=nationalite,
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
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.ClientRead:
    client = clients_crud.creer_client(db, payload, settings)
    lecture = clients_crud.to_read(client)
    emettre(db, taches, schemas.EvenementWebhook.client_cree, lecture.model_dump(mode="json"))
    for compte in client.comptes:
        emettre(db, taches, schemas.EvenementWebhook.compte_cree, comptes_crud.to_read(compte).model_dump(mode="json"))
    return lecture


@router.put("/{external_id}", response_model=schemas.ClientRead)
def modifier_client(
    external_id: str,
    payload: schemas.ClientUpdate,
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.ClientRead:
    client = _obtenir_client_ou_404(db, external_id)
    client = clients_crud.mettre_a_jour_client(db, client, payload)
    lecture = clients_crud.to_read(client)
    emettre(db, taches, schemas.EvenementWebhook.client_modifie, lecture.model_dump(mode="json"))
    return lecture


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------


@router.post(
    "/{external_id}/documents",
    response_model=schemas.DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def ajouter_document(
    external_id: str,
    payload: schemas.DocumentCreate,
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.DocumentRead:
    client = _obtenir_client_ou_404(db, external_id)
    document = clients_crud.ajouter_document(db, client, payload)
    lecture = schemas.DocumentRead.model_validate(document)
    emettre(db, taches, schemas.EvenementWebhook.document_ajoute, {"client_external_id": external_id, **lecture.model_dump(mode="json")})
    return lecture


@router.put("/{external_id}/documents/{document_id}", response_model=schemas.DocumentRead)
def modifier_document(
    external_id: str,
    document_id: str,
    payload: schemas.DocumentUpdate,
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.DocumentRead:
    client = _obtenir_client_ou_404(db, external_id)
    document = clients_crud.get_document(db, client, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    document = clients_crud.mettre_a_jour_document(db, document, payload)
    lecture = schemas.DocumentRead.model_validate(document)
    emettre(db, taches, schemas.EvenementWebhook.document_modifie, {"client_external_id": external_id, **lecture.model_dump(mode="json")})
    return lecture


@router.delete("/{external_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_document(
    external_id: str, document_id: str, taches: BackgroundTasks, db: Session = Depends(get_db)
) -> None:
    client = _obtenir_client_ou_404(db, external_id)
    document = clients_crud.get_document(db, client, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable.")
    clients_crud.supprimer_document(db, document)
    emettre(db, taches, schemas.EvenementWebhook.document_supprime, {"client_external_id": external_id, "external_id": document_id})


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
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.BeneficiaireEffectifRead:
    client = _obtenir_client_ou_404(db, external_id)
    beneficiaire = clients_crud.ajouter_beneficiaire(db, client, payload)
    lecture = schemas.BeneficiaireEffectifRead.model_validate(beneficiaire)
    emettre(db, taches, schemas.EvenementWebhook.beneficiaire_ajoute, {"client_external_id": external_id, **lecture.model_dump(mode="json")})
    return lecture


@router.put(
    "/{external_id}/beneficiaires-effectifs/{beneficiaire_id}",
    response_model=schemas.BeneficiaireEffectifRead,
)
def modifier_beneficiaire(
    external_id: str,
    beneficiaire_id: str,
    payload: schemas.BeneficiaireEffectifUpdate,
    taches: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.BeneficiaireEffectifRead:
    client = _obtenir_client_ou_404(db, external_id)
    beneficiaire = clients_crud.get_beneficiaire(db, client, beneficiaire_id)
    if beneficiaire is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bénéficiaire effectif introuvable."
        )
    beneficiaire = clients_crud.mettre_a_jour_beneficiaire(db, beneficiaire, payload)
    lecture = schemas.BeneficiaireEffectifRead.model_validate(beneficiaire)
    emettre(db, taches, schemas.EvenementWebhook.beneficiaire_modifie, {"client_external_id": external_id, **lecture.model_dump(mode="json")})
    return lecture


@router.delete(
    "/{external_id}/beneficiaires-effectifs/{beneficiaire_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def supprimer_beneficiaire(
    external_id: str, beneficiaire_id: str, taches: BackgroundTasks, db: Session = Depends(get_db)
) -> None:
    client = _obtenir_client_ou_404(db, external_id)
    beneficiaire = clients_crud.get_beneficiaire(db, client, beneficiaire_id)
    if beneficiaire is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bénéficiaire effectif introuvable."
        )
    clients_crud.supprimer_beneficiaire(db, beneficiaire)
    emettre(db, taches, schemas.EvenementWebhook.beneficiaire_supprime, {"client_external_id": external_id, "external_id": beneficiaire_id})
