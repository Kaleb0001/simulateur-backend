import hashlib
import hmac
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import Settings, get_settings
from .database import get_db
from .utils import maintenant_utc

# Ce qu'un jeton en lecture seule a le droit de faire.
METHODES_LECTURE = {"GET", "HEAD", "OPTIONS"}


@dataclass
class ApiConsumer:
    nom: str
    portee: str  # "ecriture" | "lecture"
    admin: bool


def empreinte_jeton(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def _jeton_invalide() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Jeton API invalide.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_consumer(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ApiConsumer:
    """Vérifie le header Authorization: Bearer <token>.

    Deux sortes de jetons sont acceptées :

    - SIMULATEUR_API_TOKEN (voir Settings.api_keys), le jeton d'administration,
      qui a tous les droits ;
    - le jeton d'un consommateur créé avec une connexion (table
      consommateurs_api), retrouvé par son empreinte. Révoqué, il est refusé
      (401) ; en lecture seule, il ne passe que les requêtes GET (403 sinon).

    Le nom du consommateur est stocké sur request.state pour être repris par
    le middleware de journalisation des accès.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="En-tête Authorization manquant ou invalide (format attendu : Bearer <token>).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise _jeton_invalide()

    for cle, nom in settings.api_keys.items():
        if hmac.compare_digest(cle.encode(), token.encode()):
            request.state.consommateur = nom
            return ApiConsumer(nom=nom, portee="ecriture", admin=True)

    consommateur = db.scalar(
        select(models.ConsommateurApi).where(
            models.ConsommateurApi.empreinte_jeton == empreinte_jeton(token)
        )
    )
    if consommateur is None or not consommateur.actif:
        raise _jeton_invalide()

    request.state.consommateur = consommateur.nom
    consommateur.derniere_utilisation = maintenant_utc()
    db.commit()

    if consommateur.portee == "lecture" and request.method not in METHODES_LECTURE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce jeton est en lecture seule : seules les requêtes GET sont autorisées.",
        )
    return ApiConsumer(nom=consommateur.nom, portee=consommateur.portee, admin=False)


def exiger_admin(consommateur: ApiConsumer = Depends(get_current_consumer)) -> ApiConsumer:
    """Réserve une route au jeton d'administration."""
    if not consommateur.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé au jeton d'administration.",
        )
    return consommateur
