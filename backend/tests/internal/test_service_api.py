import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.factories import (
    make_company,
    make_jurisdiction,
    make_user,
)
from tests.utils.selections import set_company_ids, set_user_ids
from tests.utils.utils import assert_error

API = settings.API_V1_STR
SERVICE_KEY = "test-service-key"
HEADERS = {"X-API-Key": SERVICE_KEY}


@pytest.fixture(autouse=True)
def service_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SERVICE_API_KEY", SERVICE_KEY)


def url(company_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"{API}/service/companies/{company_id}/users/{user_id}/jurisdiction-ids"


def active_url(
    company_id: uuid.UUID, user_id: uuid.UUID, jurisdiction_id: uuid.UUID
) -> str:
    return (
        f"{API}/service/companies/{company_id}/users/{user_id}"
        f"/jurisdictions/{jurisdiction_id}/active"
    )


def users_url(company_id: uuid.UUID, jurisdiction_id: uuid.UUID) -> str:
    return (
        f"{API}/service/companies/{company_id}/jurisdictions/{jurisdiction_id}/user-ids"
    )


def test_returns_plain_id_list_with_api_key(client: TestClient, db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j1, j2 = make_jurisdiction(db), make_jurisdiction(db)
    set_company_ids(db, company.id, [j1.id, j2.id])
    set_user_ids(db, user, [j1.id])

    r = client.get(url(company.id, user.id), headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == [str(j1.id)]


def test_superuser_token_is_accepted(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    company = make_company(db)
    user = make_user(db, company)
    r = client.get(url(company.id, user.id), headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_unknown_user_or_company_is_404(client: TestClient, db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    r = client.get(url(company.id, uuid.uuid4()), headers=HEADERS)
    assert_error(r, 404, "user_not_found")
    r = client.get(url(uuid.uuid4(), user.id), headers=HEADERS)
    assert_error(r, 404, "company_not_found")


def test_user_of_another_company_is_404(client: TestClient, db: Session) -> None:
    company, other_company = make_company(db), make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])
    set_user_ids(db, user, [j.id])

    r = client.get(url(other_company.id, user.id), headers=HEADERS)
    assert_error(r, 404, "user_not_found")
    r = client.get(active_url(other_company.id, user.id, j.id), headers=HEADERS)
    assert_error(r, 404, "user_not_found")
    r = client.get(users_url(other_company.id, j.id), headers=HEADERS)
    assert r.json() == []


def test_rejects_missing_or_wrong_credentials(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    for u in (
        url(company.id, user.id),
        active_url(company.id, user.id, j.id),
        users_url(company.id, j.id),
    ):
        assert_error(client.get(u), 401, "unauthorized")
        r = client.get(u, headers={"X-API-Key": "nope"})
        assert_error(r, 401, "invalid_api_key")
        # Company admins and regular users are not service callers
        r = client.get(u, headers=normal_user_token_headers)
        assert_error(r, 403, "forbidden")


def test_key_auth_disabled_when_unset(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SERVICE_API_KEY", None)
    company = make_company(db)
    user = make_user(db, company)
    r = client.get(url(company.id, user.id), headers=HEADERS)
    assert_error(r, 401, "invalid_api_key")


def test_inactive_user_or_company_monitors_nothing(
    client: TestClient, db: Session
) -> None:
    company = make_company(db)
    user, other = make_user(db, company), make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])
    for u in (user, other):
        set_user_ids(db, u, [j.id])

    user.is_active = False
    db.add(user)
    db.commit()
    assert client.get(url(company.id, user.id), headers=HEADERS).json() == []
    r = client.get(url(company.id, other.id), headers=HEADERS)
    assert r.json() == [str(j.id)]

    company.is_active = False
    db.add(company)
    db.commit()
    r = client.get(url(company.id, other.id), headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == []


def test_non_ascii_api_key_is_rejected(client: TestClient, db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    r = client.get(url(company.id, user.id), headers={"X-API-Key": b"cl\xe9"})
    assert_error(r, 401, "invalid_api_key")


def test_active_check_returns_bool(client: TestClient, db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    on, licensed_off, unlicensed = (make_jurisdiction(db) for _ in range(3))
    set_company_ids(db, company.id, [on.id, licensed_off.id])
    set_user_ids(db, user, [on.id])

    r = client.get(active_url(company.id, user.id, on.id), headers=HEADERS)
    assert r.json() is True
    for j in (licensed_off, unlicensed):
        r = client.get(active_url(company.id, user.id, j.id), headers=HEADERS)
        assert r.status_code == 200
        assert r.json() is False


def test_active_check_is_false_for_inactive_user_or_company(
    client: TestClient, db: Session
) -> None:
    company = make_company(db)
    user, other = make_user(db, company), make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])
    for u in (user, other):
        set_user_ids(db, u, [j.id])

    user.is_active = False
    db.add(user)
    db.commit()
    r = client.get(active_url(company.id, user.id, j.id), headers=HEADERS)
    assert r.json() is False
    r = client.get(active_url(company.id, other.id, j.id), headers=HEADERS)
    assert r.json() is True

    company.is_active = False
    db.add(company)
    db.commit()
    r = client.get(active_url(company.id, other.id, j.id), headers=HEADERS)
    assert r.json() is False


def test_active_check_unknown_jurisdiction_is_404(
    client: TestClient, db: Session
) -> None:
    company = make_company(db)
    user = make_user(db, company)
    r = client.get(active_url(company.id, user.id, uuid.uuid4()), headers=HEADERS)
    assert_error(r, 404, "jurisdiction_not_found")


def test_user_ids_lists_active_users_with_the_jurisdiction(
    client: TestClient, db: Session
) -> None:
    company, other_company = make_company(db), make_company(db)
    a, b, without, inactive = (make_user(db, company) for _ in range(4))
    outsider = make_user(db, other_company)
    j, k = make_jurisdiction(db), make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id, k.id])
    set_company_ids(db, other_company.id, [j.id])
    for u in (a, b, inactive):
        set_user_ids(db, u, [j.id])
    set_user_ids(db, without, [k.id])
    set_user_ids(db, outsider, [j.id])
    inactive.is_active = False
    db.add(inactive)
    db.commit()

    r = client.get(users_url(company.id, j.id), headers=HEADERS)
    assert r.status_code == 200
    by_email = sorted((a, b), key=lambda u: u.email)
    assert r.json() == [str(u.id) for u in by_email]


def test_user_ids_empty_for_inactive_company(client: TestClient, db: Session) -> None:
    company = make_company(db)
    user = make_user(db, company)
    j = make_jurisdiction(db)
    set_company_ids(db, company.id, [j.id])
    set_user_ids(db, user, [j.id])
    company.is_active = False
    db.add(company)
    db.commit()

    r = client.get(users_url(company.id, j.id), headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == []


def test_user_ids_unknown_company_or_jurisdiction_is_404(
    client: TestClient, db: Session
) -> None:
    company = make_company(db)
    j = make_jurisdiction(db)
    r = client.get(users_url(uuid.uuid4(), j.id), headers=HEADERS)
    assert_error(r, 404, "company_not_found")
    r = client.get(users_url(company.id, uuid.uuid4()), headers=HEADERS)
    assert_error(r, 404, "jurisdiction_not_found")
