import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from tests.crud.test_company_jurisdiction import (
    make_company,
    make_jurisdiction,
    make_user,
)

API = settings.API_V1_STR
SERVICE_KEY = "test-service-key"


@pytest.fixture(autouse=True)
def service_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SERVICE_API_KEY", SERVICE_KEY)


def url(user_id: uuid.UUID) -> str:
    return f"{API}/service/users/{user_id}/jurisdiction-ids"


def test_returns_plain_id_list_with_api_key(client: TestClient, db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j1, j2 = make_jurisdiction(db), make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[j1.id, j2.id]
    )
    crud.set_user_jurisdictions(session=db, user=user, jurisdiction_ids=[j1.id])

    r = client.get(url(user.id), headers={"X-API-Key": SERVICE_KEY})
    assert r.status_code == 200
    assert r.json() == [str(j1.id)]


def test_superuser_token_is_accepted(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    user = make_user(db, make_company(db))
    r = client.get(url(user.id), headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_unknown_user_is_404(client: TestClient) -> None:
    r = client.get(url(uuid.uuid4()), headers={"X-API-Key": SERVICE_KEY})
    assert r.status_code == 404


def test_rejects_missing_or_wrong_credentials(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    user = make_user(db, make_company(db))
    assert client.get(url(user.id)).status_code == 401
    assert client.get(url(user.id), headers={"X-API-Key": "nope"}).status_code == 401
    # Company admins and regular users are not service callers
    assert (
        client.get(url(user.id), headers=normal_user_token_headers).status_code == 403
    )


def test_key_auth_disabled_when_unset(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SERVICE_API_KEY", None)
    user = make_user(db, make_company(db))
    r = client.get(url(user.id), headers={"X-API-Key": SERVICE_KEY})
    assert r.status_code == 401
