from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status

from .config import Settings, get_settings


@dataclass
class ApiConsumer:
    nom: str


def get_current_consumer(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> ApiConsumer:
    """Verifie le header Authorization: Bearer <token>.

    La cle attendue est configurable via la variable d'environnement
    SIMULATEUR_API_TOKEN (voir Settings.api_keys). Le nom du consommateur
    resolu est stocke sur request.state pour etre repris par le middleware
    de journalisation des acces.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="En-tête Authorization manquant ou invalide (format attendu : Bearer <token>).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    consumer_name = settings.api_keys.get(token)
    if consumer_name is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton API invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.consommateur = consumer_name
    return ApiConsumer(nom=consumer_name)
