from fastapi import FastAPI

from .database import Base, engine
from .middleware import JournalAccesMiddleware
from .migrations import adapter_schema
from .routers import clients, comptes, journal, transactions

Base.metadata.create_all(bind=engine)
adapter_schema(engine)

app = FastAPI(
    title="Simulateur de système de gestion interne d'IMF",
    description=(
        "API de gestion interne (clients, comptes, transactions) exposée par "
        "une IMF pour ses propres besoins, et consultable par des systèmes "
        "tiers (ex. Vigie) qui viennent y récupérer ce dont ils ont besoin. "
        "Ce système n'émet lui-même aucun appel sortant."
    ),
    version="2.0.0",
)

app.add_middleware(JournalAccesMiddleware)

app.include_router(clients.router)
app.include_router(comptes.router)
app.include_router(transactions.router)
app.include_router(journal.router)


@app.get("/", tags=["Racine"])
def racine() -> dict[str, str]:
    return {
        "service": "simulateur-imf",
        "documentation": "/docs",
    }
