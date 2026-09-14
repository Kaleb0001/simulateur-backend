from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from .. import schemas
from ..config import Settings, get_settings
from ..crud import connexions as crud
from ..database import get_db
from ..security import exiger_admin

router = APIRouter(
    prefix="/api/v1/connexions",
    tags=["Connexions"],
    dependencies=[Depends(exiger_admin)],
)


@router.post("", response_model=schemas.ConnexionCreee, status_code=status.HTTP_201_CREATED)
def creer_connexion(
    payload: schemas.ConnexionCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.ConnexionCreee:
    """Connecte un système tiers : un abonnement webhook (si `url_reception`
    est fourni) et un jeton API en lecture seule limité aux données de
    `acces` (si la liste n'est pas vide). Le jeton et le secret ne sont
    renvoyés qu'ici ; ils restent valables jusqu'à la révocation."""
    return crud.creer_connexion(db, payload, settings)


@router.get("", response_model=schemas.ConnexionsListResponse)
def lister_connexions(
    limite: int = Query(default=50, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.ConnexionsListResponse:
    total, resultats = crud.lister_connexions(db, limite, decalage)
    return schemas.ConnexionsListResponse(
        total=total, limite=limite, decalage=decalage, resultats=[crud.to_read(c) for c in resultats]
    )


@router.get("/{external_id}", response_model=schemas.ConnexionRead)
def obtenir_connexion(external_id: str, db: Session = Depends(get_db)) -> schemas.ConnexionRead:
    return crud.to_read(crud.obtenir_connexion(db, external_id))


@router.put("/{external_id}", response_model=schemas.ConnexionModifiee)
def modifier_connexion(
    external_id: str,
    payload: schemas.ConnexionUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.ConnexionModifiee:
    """Change le nom, l'adresse de réception, les événements ou les accès,
    sans changer le jeton ni le secret."""
    return crud.modifier_connexion(db, crud.obtenir_connexion(db, external_id), payload, settings)


@router.post("/{external_id}/revoquer", response_model=schemas.ConnexionRead)
def revoquer_connexion(external_id: str, db: Session = Depends(get_db)) -> schemas.ConnexionRead:
    """Désactive le jeton API et l'abonnement webhook de la connexion."""
    return crud.to_read(crud.revoquer_connexion(db, crud.obtenir_connexion(db, external_id)))
