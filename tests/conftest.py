import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_DB_FILE = Path(tempfile.gettempdir()) / "simulateur_imf_test.db"
_DB_FILE.unlink(missing_ok=True)

os.environ["SIMULATEUR_API_TOKEN"] = "test-token"
os.environ["WEBHOOK_DELAI_ENTRE_TENTATIVES_SECONDES"] = "0"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE.as_posix()}"
os.environ["URL_PUBLIQUE_API"] = "http://127.0.0.1:8011/api/v1"

import pytest
from fastapi.testclient import TestClient

from app.main import app

HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
