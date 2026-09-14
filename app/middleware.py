import anyio
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .database import SessionLocal
from .models import JournalAcces

CHEMINS_EXCLUS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}


class LimiteRequetesSimultanees:
    """Plafonne le nombre de requêtes traitées en même temps ; les suivantes
    attendent leur tour au lieu d'être refusées.

    Sans ce plafond, une rafale de lectures (la passerelle n8n en envoie
    beaucoup à la fois) épuise le pool de connexions : des requêtes tiennent
    une connexion en attendant un fil de travail, pendant que les fils
    attendent une connexion, jusqu'à l'expiration du délai du pool. Chaque
    requête utilise au plus deux connexions et deux fils (la sienne et celle
    du journal des accès) : un plafond inférieur à la moitié du pool et des
    fils écarte ce blocage.

    La place est rendue dès la réponse envoyée, sans attendre les tâches de
    fond (envoi des webhooks).
    """

    def __init__(self, app, maximum: int) -> None:
        self.app = app
        self.maximum = maximum
        self._semaphore: anyio.Semaphore | None = None

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self._semaphore is None:
            self._semaphore = anyio.Semaphore(self.maximum)
        semaphore = self._semaphore
        await semaphore.acquire()
        liberee = False

        def liberer() -> None:
            nonlocal liberee
            if not liberee:
                liberee = True
                semaphore.release()

        async def envoyer(message) -> None:
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                liberer()

        try:
            await self.app(scope, receive, envoyer)
        finally:
            liberer()


class JournalAccesMiddleware(BaseHTTPMiddleware):
    """Journalise chaque requête reçue par l'API.

    Utile pendant la démo pour visualiser en direct le moment où Vigie (ou
    tout autre consommateur) vient interroger l'API, puisque ce système
    n'émet plus lui-même aucun appel sortant.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if request.url.path not in CHEMINS_EXCLUS:
            # L'écriture est bloquante : hors de la boucle d'événements, elle
            # n'arrête pas les autres requêtes pendant qu'elle attend une
            # connexion du pool.
            await run_in_threadpool(self._enregistrer, request, response)

        return response

    @staticmethod
    def _enregistrer(request: Request, response: Response) -> None:
        db = SessionLocal()
        try:
            entree = JournalAcces(
                methode=request.method,
                chemin=request.url.path,
                statut_code=response.status_code,
                consommateur=getattr(request.state, "consommateur", None),
            )
            db.add(entree)
            db.commit()
        finally:
            db.close()
