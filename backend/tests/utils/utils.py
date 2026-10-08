import random
import string
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from app.core.config import settings


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def assert_error(r: Response, status_code: int, code: str) -> dict[str, Any]:
    """Assert an error response's status and envelope `code`; return the body."""
    assert r.status_code == status_code, r.text
    body: dict[str, Any] = r.json()
    assert body["code"] == code, body
    return body
