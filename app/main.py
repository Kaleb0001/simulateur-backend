from fastapi import FastAPI

from .database import Base, engine
from .middleware import JournalAccesMiddleware
from .migrations import (
    adapter_schema,
    normaliser_referentiels,
    peupler_referentiels,
    supprimer_colonnes_retirees,
)
from .routers import clients, comptes, connexions, journal, referentiels, transactions, webhooks

Base.metadata.create_all(bind=engine)
adapter_schema(engine)
supprimer_colonnes_retirees(engine)
peupler_referentiels(engine)
normaliser_referentiels(engine)

app = FastAPI(
    title="Simulateur de système de gestion interne d'IMF",
    description=(
        "API de gestion interne (clients, comptes, transactions) exposée par "
        "une IMF pour ses propres besoins, et consultable par des systèmes "
        "tiers (ex. Vigie) qui viennent y récupérer ce dont ils ont besoin, ou "
        "qui s'abonnent à ses événements par webhook."
    ),
    version="2.0.0",
)

app.add_middleware(JournalAccesMiddleware)

app.include_router(clients.router)
app.include_router(comptes.router)
app.include_router(transactions.router)
app.include_router(journal.router)
app.include_router(webhooks.router)
app.include_router(referentiels.router)
app.include_router(connexions.router)


@app.get("/", tags=["Racine"])
def racine() -> dict[str, str]:
    return {
        "service": "simulateur-imf",
        "documentation": "/docs",
    }
