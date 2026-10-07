import os
from collections.abc import Generator
from pathlib import Path

# Use a separate database so the tests never touch the dev data in app.db.
# Must be set before app.core.config is imported; env vars take precedence over .env
BACKEND_DIR = Path(__file__).parents[1]
TEST_DB_FILE = BACKEND_DIR / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE.as_posix()}"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.utils.user import authentication_token_from_email  # noqa: E402
from tests.utils.utils import get_superuser_token_headers  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    # Start every run from a fresh, fully migrated database
    engine.dispose()
    TEST_DB_FILE.unlink(missing_ok=True)
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    with Session(engine) as session:
        init_db(session)
        yield session


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
