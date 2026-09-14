import json
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from .. import webhooks as service
from ..database import get_db
from ..security import get_current_consumer
from ..crud.connexions import connexion_de_l_abonnement
from ..utils import generer_external_id, paginer

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
    dependencies=[Depends(get_current_consumer)],
)


def _abonnement_ou_404(db: Session, external_id: str) -> models.WebhookAbonnement:
    abonnement = db.scalar(
        select(models.WebhookAbonnement).where(models.WebhookAbonnement.external_id == external_id)
    )
    if abonnement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable.")
    return abonnement


@router.get("/evenements", response_model=list[schemas.EvenementWebhook])
def lister_evenements() -> list[schemas.EvenementWebhook]:
    """Les événements auxquels un abonné peut s'inscrire."""
    return [e for e in schemas.EvenementWebhook if e != schemas.EvenementWebhook.ping]


@router.get("", response_model=schemas.WebhookAbonnementsListResponse)
def lister_abonnements(
    limite: int = Query(default=50, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.WebhookAbonnementsListResponse:
    stmt = select(models.WebhookAbonnement).order_by(models.WebhookAbonnement.id.desc())
    total, resultats = paginer(db, stmt, limite, decalage)
    return schemas.WebhookAbonnementsListResponse(
        total=total, limite=limite, decalage=decalage, resultats=[service.to_read(a) for a in resultats]
    )


@router.post("", response_model=schemas.WebhookAbonnementCree, status_code=status.HTTP_201_CREATED)
def creer_abonnement(
    payload: schemas.WebhookAbonnementCreate, db: Session = Depends(get_db)
) -> schemas.WebhookAbonnementCree:
    secret = payload.secret or secrets.token_urlsafe(32)
    abonnement = models.WebhookAbonnement(
        external_id="",
        url=str(payload.url),
        description=payload.description,
        evenements=json.dumps([e.value for e in payload.evenements]),
        secret=secret,
        actif=payload.actif,
    )
    db.add(abonnement)
    db.flush()
    abonnement.external_id = generer_external_id("WH-EXT", abonnement.id)
    db.commit()
    db.refresh(abonnement)
    return schemas.WebhookAbonnementCree(**service.to_read(abonnement).model_dump(), secret=secret)


@router.get("/{external_id}", response_model=schemas.WebhookAbonnementRead)
def obtenir_abonnement(external_id: str, db: Session = Depends(get_db)) -> schemas.WebhookAbonnementRead:
    return service.to_read(_abonnement_ou_404(db, external_id))


@router.put("/{external_id}", response_model=schemas.WebhookAbonnementRead)
def modifier_abonnement(
    external_id: str, payload: schemas.WebhookAbonnementUpdate, db: Session = Depends(get_db)
) -> schemas.WebhookAbonnementRead:
    abonnement = _abonnement_ou_404(db, external_id)
    donnees = payload.model_dump(exclude_unset=True)
    if donnees.get("url") is not None:
        abonnement.url = str(donnees["url"])
    if "description" in donnees:
        abonnement.description = donnees["description"]
    if donnees.get("evenements") is not None:
        abonnement.evenements = json.dumps([schemas.EvenementWebhook(e).value for e in donnees["evenements"]])
    if donnees.get("actif") is not None:
        connexion = connexion_de_l_abonnement(db, abonnement)
        if donnees["actif"] and connexion is not None and connexion.statut == schemas.StatutConnexion.revoquee.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cet abonnement appartient à la connexion révoquée {connexion.external_id}.",
            )
        abonnement.actif = donnees["actif"]
    db.commit()
    db.refresh(abonnement)
    return service.to_read(abonnement)


@router.delete("/{external_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_abonnement(external_id: str, db: Session = Depends(get_db)) -> None:
    abonnement = _abonnement_ou_404(db, external_id)
    connexion = connexion_de_l_abonnement(db, abonnement)
    if connexion is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cet abonnement appartient à la connexion {connexion.external_id} : révoquez la connexion.",
        )
    db.delete(abonnement)
    db.commit()


@router.post("/{external_id}/test", response_model=schemas.WebhookLivraisonRead, status_code=status.HTTP_202_ACCEPTED)
def tester_abonnement(
    external_id: str, taches: BackgroundTasks, db: Session = Depends(get_db)
) -> schemas.WebhookLivraisonRead:
    """Envoie un événement « ping » à cet abonné, même inactif."""
    abonnement = _abonnement_ou_404(db, external_id)
    livraison = service.preparer_livraison(
        db, abonnement, schemas.EvenementWebhook.ping.value, {"message": "Test de l'abonnement."}
    )
    db.commit()
    db.refresh(livraison)
    taches.add_task(service.livrer, livraison.external_id)
    return service.livraison_to_read(livraison)


@router.get("/{external_id}/livraisons", response_model=schemas.WebhookLivraisonsListResponse)
def lister_livraisons(
    external_id: str,
    limite: int = Query(default=50, ge=1, le=200),
    decalage: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.WebhookLivraisonsListResponse:
    abonnement = _abonnement_ou_404(db, external_id)
    stmt = (
        select(models.WebhookLivraison)
        .where(models.WebhookLivraison.abonnement_id == abonnement.id)
        .order_by(models.WebhookLivraison.id.desc())
    )
    total, resultats = paginer(db, stmt, limite, decalage)
    return schemas.WebhookLivraisonsListResponse(
        total=total, limite=limite, decalage=decalage,
        resultats=[service.livraison_to_read(l) for l in resultats],
    )


@router.post("/livraisons/{livraison_id}/renvoyer", response_model=schemas.WebhookLivraisonRead, status_code=status.HTTP_202_ACCEPTED)
def renvoyer_livraison(
    livraison_id: str, taches: BackgroundTasks, db: Session = Depends(get_db)
) -> schemas.WebhookLivraisonRead:
    livraison = db.scalar(
        select(models.WebhookLivraison).where(models.WebhookLivraison.external_id == livraison_id)
    )
    if livraison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livraison introuvable.")
    livraison.statut = "en_attente"
    db.commit()
    db.refresh(livraison)
    taches.add_task(service.livrer, livraison.external_id)
    return service.livraison_to_read(livraison)
