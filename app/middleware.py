from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .database import SessionLocal
from .models import JournalAcces

CHEMINS_EXCLUS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}


class JournalAccesMiddleware(BaseHTTPMiddleware):
    """Journalise chaque requête reçue par l'API.

    Utile pendant la démo pour visualiser en direct le moment où Vigie (ou
    tout autre consommateur) vient interroger l'API, puisque ce système
    n'émet plus lui-même aucun appel sortant.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if request.url.path not in CHEMINS_EXCLUS:
            self._enregistrer(request, response)

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
