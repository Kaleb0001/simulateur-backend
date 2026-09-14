from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .schemas import TypeCompte


class Settings(BaseSettings):
    """Configuration de l'application, lue depuis les variables d'environnement / .env.

    Aucune valeur sensible ou de paramétrage métier n'est codée en dur ailleurs
    dans le code : tout passe par cet objet.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    simulateur_api_token: str = "change-moi-en-production"

    type_compte_par_defaut: TypeCompte = TypeCompte.courant
    devise_par_defaut: str = "XOF"
    solde_initial_par_defaut: float = 0
    prefixe_numero_compte: str = "CPT"

    # PostgreSQL en fonctionnement normal (voir infra/postgres) ; une URL
    # SQLite reste acceptée, par exemple pour un essai sans serveur.
    database_url: str = "sqlite:///./simulateur_imf.db"
    # Pool de connexions (PostgreSQL).
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_pool_timeout_secondes: float = 10.0
    # Requêtes traitées en même temps, les suivantes attendent leur tour
    # (voir middleware.LimiteRequetesSimultanees). À garder sous la moitié du
    # pool et des 40 fils de travail.
    requetes_simultanees_max: int = 15

    # Adresse de l'API telle qu'un système tiers la joint, renvoyée avec son
    # jeton à la création d'une connexion.
    url_publique_api: str = "http://127.0.0.1:8011/api/v1"

    # Webhooks sortants
    webhook_timeout_secondes: float = 5.0
    webhook_tentatives_max: int = 3
    webhook_delai_entre_tentatives_secondes: float = 2.0

    @field_validator("database_url")
    @classmethod
    def _normaliser_database_url(cls, valeur: str) -> str:
        return normaliser_database_url(valeur)

    @property
    def api_keys(self) -> dict[str, str]:
        """Associe chaque jeton API valide au nom de son consommateur.

        Une seule clé partagée suffit pour la démo (SIMULATEUR_API_TOKEN),
        mais la forme en dict permet d'ajouter facilement d'autres
        clés/consommateurs plus tard (ex. une clé dédiée pour IMF SHIELD et une
        autre pour le futur frontend) sans changer le code appelant.
        """
        keys: dict[str, str] = {}
        if self.simulateur_api_token:
            keys[self.simulateur_api_token] = "default"
        return keys


def normaliser_database_url(url: str) -> str:
    """Ramène les formes courtes d'une URL PostgreSQL (postgres://,
    postgresql://) au pilote psycopg 3, le seul installé."""
    for prefixe in ("postgres://", "postgresql://"):
        if url.startswith(prefixe):
            return "postgresql+psycopg://" + url.removeprefix(prefixe)
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
