import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_DB_FILE = Path(tempfile.gettempdir()) / "simulateur_imf_test.db"
_DB_FILE.unlink(missing_ok=True)

os.environ["SIMULATEUR_API_TOKEN"] = "test-token"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE.as_posix()}"

import pytest
from fastapi.testclient import TestClient

from app.main import app

HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
