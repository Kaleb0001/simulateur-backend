"""Configuration commune des tests.

Les tests tournent sur la base PostgreSQL de test (simulateur_imf_test, créée
par infra/postgres), vidée et recréée à chaque session. L'URL vient de
TEST_DATABASE_URL ; à défaut, elle est déduite de DATABASE_URL (environnement
ou .env) en remplaçant le nom de la base par « simulateur_imf_test ». Seule
une base dont le nom finit par « _test » est vidée.

Les tests de mise à niveau SQLite (test_migrations.py) créent leurs propres
bases SQLite temporaires.
"""

import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import MetaData, make_url

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.config import normaliser_database_url  # noqa: E402


def _url_de_test() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return normaliser_database_url(url)
    principale = os.environ.get("DATABASE_URL") or dotenv_values(RACINE / ".env").get("DATABASE_URL")
    if not principale or not normaliser_database_url(principale).startswith("postgresql"):
        raise RuntimeError(
            "Base de test introuvable : définir TEST_DATABASE_URL (PostgreSQL, "
            "ex. postgresql://simulateur:<mot de passe>@localhost:5434/simulateur_imf_test)."
        )
    return make_url(normaliser_database_url(principale)).set(
        database="simulateur_imf_test"
    ).render_as_string(hide_password=False)


TEST_DATABASE_URL = _url_de_test()
_nom_base = make_url(TEST_DATABASE_URL).database or ""
if TEST_DATABASE_URL.startswith("postgresql") and not _nom_base.endswith("_test"):
    raise RuntimeError(f"Refus de vider la base « {_nom_base} » : son nom doit finir par « _test ».")

os.environ["SIMULATEUR_API_TOKEN"] = "test-token"
os.environ["WEBHOOK_DELAI_ENTRE_TENTATIVES_SECONDES"] = "0"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["URL_PUBLIQUE_API"] = "http://127.0.0.1:8011/api/v1"

from app.database import engine  # noqa: E402

# Repart d'une base vide : toutes les tables présentes, y compris celles
# d'une version antérieure du modèle, sont supprimées avant que l'import de
# l'application ne recrée le schéma.
_existantes = MetaData()
_existantes.reflect(bind=engine)
_existantes.drop_all(bind=engine)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
