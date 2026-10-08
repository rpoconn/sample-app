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
from tests.utils.utils import assert_error

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
    assert_error(r, 404, "user_not_found")


def test_rejects_missing_or_wrong_credentials(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    user = make_user(db, make_company(db))
    assert_error(client.get(url(user.id)), 401, "unauthorized")
    r = client.get(url(user.id), headers={"X-API-Key": "nope"})
    assert_error(r, 401, "invalid_api_key")
    # Company admins and regular users are not service callers
    r = client.get(url(user.id), headers=normal_user_token_headers)
    assert_error(r, 403, "forbidden")


def test_key_auth_disabled_when_unset(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SERVICE_API_KEY", None)
    user = make_user(db, make_company(db))
    r = client.get(url(user.id), headers={"X-API-Key": SERVICE_KEY})
    assert_error(r, 401, "invalid_api_key")


def test_inactive_user_or_company_monitors_nothing(
    client: TestClient, db: Session
) -> None:
    company = make_company(db)
    user, other = make_user(db, company), make_user(db, company)
    j = make_jurisdiction(db)
    crud.set_company_jurisdictions(
        session=db, company_id=company.id, jurisdiction_ids=[j.id]
    )
    for u in (user, other):
        crud.set_user_jurisdictions(session=db, user=u, jurisdiction_ids=[j.id])
    headers = {"X-API-Key": SERVICE_KEY}

    user.is_active = False
    db.add(user)
    db.commit()
    assert client.get(url(user.id), headers=headers).json() == []
    assert client.get(url(other.id), headers=headers).json() == [str(j.id)]

    company.is_active = False
    db.add(company)
    db.commit()
    r = client.get(url(other.id), headers=headers)
    assert r.status_code == 200
    assert r.json() == []
