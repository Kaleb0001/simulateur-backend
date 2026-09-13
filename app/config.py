from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application, lue depuis les variables d'environnement / .env.

    Aucune valeur sensible ou de paramétrage métier n'est codée en dur ailleurs
    dans le code : tout passe par cet objet.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    simulateur_api_token: str = "change-moi-en-production"

    type_compte_par_defaut: str = "Courant"
    devise_par_defaut: str = "XOF"
    solde_initial_par_defaut: float = 0
    prefixe_numero_compte: str = "CPT"

    database_url: str = "sqlite:///./simulateur_imf.db"

    @property
    def api_keys(self) -> dict[str, str]:
        """Associe chaque jeton API valide au nom de son consommateur.

        Une seule clé partagée suffit pour la démo (SIMULATEUR_API_TOKEN),
        mais la forme en dict permet d'ajouter facilement d'autres
        clés/consommateurs plus tard (ex. une clé dédiée pour Vigie et une
        autre pour le futur frontend) sans changer le code appelant.
        """
        keys: dict[str, str] = {}
        if self.simulateur_api_token:
            keys[self.simulateur_api_token] = "default"
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
