from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import UserCreate
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


def assert_envelope(body: dict, code: str) -> None:
    assert set(body) == {"detail", "code", "context"}
    assert isinstance(body["detail"], str)
    assert body["code"] == code
    assert isinstance(body["context"], dict)


def test_api_error_envelope(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/00000000-0000-0000-0000-000000000000",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404
    assert_envelope(r.json(), "user_not_found")


def test_routing_404_envelope(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/no-such-route")
    assert r.status_code == 404
    assert_envelope(r.json(), "not_found")


def test_routing_405_envelope(client: TestClient) -> None:
    r = client.delete(f"{settings.API_V1_STR}/login/access-token")
    assert r.status_code == 405
    assert_envelope(r.json(), "method_not_allowed")


def test_validation_422_envelope(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/not-a-uuid", headers=superuser_token_headers
    )
    assert r.status_code == 422
    body = r.json()
    assert_envelope(body, "invalid_input")
    errors = body["context"]["errors"]
    assert errors and body["detail"] == errors[0]["msg"]


def test_missing_token_401_has_www_authenticate(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert_envelope(r.json(), "unauthorized")


def test_bad_token_401_has_www_authenticate(client: TestClient) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert_envelope(r.json(), "invalid_token")


def test_inactive_user_403(client: TestClient, db: Session) -> None:
    email, password = random_email(), random_lower_string()
    user = crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password)
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    user.is_active = False
    db.add(user)
    db.commit()

    r = client.get(f"{settings.API_V1_STR}/users/me", headers=headers)
    assert r.status_code == 403
    assert_envelope(r.json(), "user_inactive")
