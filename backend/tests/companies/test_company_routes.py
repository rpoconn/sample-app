import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from app.companies.company_models import (
    DEFAULT_COMPANY_ID,
    Company,
    CompanyCreate,
    CompanyRole,
)
from app.companies.company_service import create_company
from app.core.config import settings
from tests.utils.factories import Account, Setup, make_account
from tests.utils.utils import assert_error, random_lower_string

API = settings.API_V1_STR


def test_create_company_superuser_only(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    name = random_lower_string()
    r = client.post(
        f"{API}/companies", headers=superuser_token_headers, json={"name": name}
    )
    assert r.status_code == 200
    assert r.json()["name"] == name

    r = client.post(
        f"{API}/companies", headers=superuser_token_headers, json={"name": name}
    )
    assert_error(r, 409, "company_name_taken")

    r = client.post(
        f"{API}/companies",
        headers=s.admin.headers,
        json={"name": random_lower_string()},
    )
    assert_error(r, 403, "forbidden")


def test_read_company_members_only(client: TestClient, s: Setup) -> None:
    r = client.get(f"{API}/companies/{s.company.id}", headers=s.member.headers)
    assert r.status_code == 200
    r = client.get(f"{API}/companies/{s.company.id}", headers=s.other_admin.headers)
    assert_error(r, 403, "forbidden")


def test_user_public_includes_company(client: TestClient, s: Setup) -> None:
    r = client.get(f"{API}/users/me", headers=s.admin.headers)
    assert r.json()["company_id"] == str(s.company.id)
    assert r.json()["company_role"] == "admin"


def test_company_admins_visible_to_members(
    client: TestClient, db: Session, s: Setup
) -> None:
    inactive = make_account(client, db, s.company, CompanyRole.admin)
    inactive.user.is_active = False
    db.add(inactive.user)
    db.commit()
    url = f"{API}/companies/{s.company.id}/admins"

    r = client.get(url, headers=s.member.headers)
    assert r.status_code == 200
    # Members and inactive admins are left out
    assert r.json() == {
        "data": [{"email": s.admin.user.email, "full_name": None}],
        "count": 1,
    }
    assert_error(client.get(url, headers=s.other_admin.headers), 403, "forbidden")


def test_inactive_company_locks_out_members(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    superuser = make_account(client, db, s.company, CompanyRole.member, superuser=True)
    r = client.patch(
        f"{API}/companies/{s.company.id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert r.status_code == 200

    r = client.get(f"{API}/users/me", headers=s.member.headers)
    assert_error(r, 403, "company_inactive")
    r = client.post(
        f"{API}/login/access-token",
        data={"username": s.member.user.email, "password": s.member.password},
    )
    body = assert_error(r, 400, "invalid_grant")
    assert body["detail"] == "Company is inactive"

    # Superusers are not tenants, so their company's state doesn't apply
    assert client.get(f"{API}/users/me", headers=superuser.headers).status_code == 200
    r = client.post(
        f"{API}/login/access-token",
        data={"username": superuser.user.email, "password": superuser.password},
    )
    assert r.status_code == 200


def test_default_company_cannot_be_deactivated(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.patch(
        f"{API}/companies/{DEFAULT_COMPANY_ID}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert_error(r, 409, "cannot_deactivate_default_company")


REMOVE_ADMIN = ["demote", "deactivate", "move", "delete_me", "delete"]


def _remove_admin(
    client: TestClient,
    superuser_headers: dict[str, str],
    admin: Account,
    target: Company,
    how: str,
) -> Response:
    url = f"{API}/users/{admin.user.id}"
    if how == "delete_me":
        return client.delete(f"{API}/users/me", headers=admin.headers)
    if how == "delete":
        return client.delete(url, headers=superuser_headers)
    body = {
        "demote": {"company_role": "member"},
        "deactivate": {"is_active": False},
        "move": {"company_id": str(target.id)},
    }[how]
    return client.patch(url, headers=superuser_headers, json=body)


@pytest.mark.parametrize("how", REMOVE_ADMIN)
def test_company_keeps_an_active_admin(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    s: Setup,
    how: str,
) -> None:
    r = _remove_admin(client, superuser_token_headers, s.admin, s.other_company, how)
    body = assert_error(r, 409, "last_company_admin")
    assert body["context"] == {"company_id": str(s.company.id)}

    make_account(client, db, s.company, CompanyRole.admin)
    r = _remove_admin(client, superuser_token_headers, s.admin, s.other_company, how)
    assert r.status_code == 200


@pytest.mark.parametrize("how", REMOVE_ADMIN)
def test_sole_user_admin_can_leave(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    s: Setup,
    how: str,
) -> None:
    company = create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    admin = make_account(client, db, company, CompanyRole.admin)
    r = _remove_admin(client, superuser_token_headers, admin, s.other_company, how)
    assert r.status_code == 200


def test_company_move_resets_role(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    mover = make_account(client, db, s.company, CompanyRole.admin)
    r = client.patch(
        f"{API}/users/{mover.user.id}",
        headers=superuser_token_headers,
        json={"company_id": str(s.other_company.id)},
    )
    assert r.status_code == 200
    assert (r.json()["company_id"], r.json()["company_role"]) == (
        str(s.other_company.id),
        "member",
    )

    # An explicit role in the same request is kept
    r = client.patch(
        f"{API}/users/{mover.user.id}",
        headers=superuser_token_headers,
        json={"company_id": str(s.company.id), "company_role": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["company_role"] == "admin"
