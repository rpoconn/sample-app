from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    Company,
    CompanyCreate,
    CompanyRole,
    Jurisdiction,
    JurisdictionCreate,
    User,
    UserCreate,
)
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


@dataclass
class Account:
    user: User
    headers: dict[str, str]


@dataclass
class Setup:
    company: Company
    other_company: Company
    admin: Account
    member: Account
    other_admin: Account
    allowed: Jurisdiction
    not_allowed: Jurisdiction
    structural: Jurisdiction


def _account(
    client: TestClient, db: Session, company: Company, role: CompanyRole
) -> Account:
    email, password = random_email(), random_lower_string()
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=email, password=password, company_id=company.id, company_role=role
        ),
    )
    return Account(
        user, user_authentication_headers(client=client, email=email, password=password)
    )


def _jurisdiction(db: Session, *, structural: bool = False) -> Jurisdiction:
    return crud.create_jurisdiction(
        session=db,
        jurisdiction_in=JurisdictionCreate(
            name=random_lower_string(), is_structural=structural
        ),
    )


@pytest.fixture
def s(client: TestClient, db: Session) -> Setup:
    company = crud.create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    other = crud.create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    return Setup(
        company=company,
        other_company=other,
        admin=_account(client, db, company, CompanyRole.admin),
        member=_account(client, db, company, CompanyRole.member),
        other_admin=_account(client, db, other, CompanyRole.admin),
        allowed=_jurisdiction(db),
        not_allowed=_jurisdiction(db),
        structural=_jurisdiction(db, structural=True),
    )


def _ids(r) -> set[str]:  # type: ignore[no-untyped-def]
    return {j["id"] for j in r.json()["data"]}


def test_create_company_superuser_only(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    name = random_lower_string()
    r = client.post(
        f"{API}/companies/", headers=superuser_token_headers, json={"name": name}
    )
    assert r.status_code == 200
    assert r.json()["name"] == name

    r = client.post(
        f"{API}/companies/", headers=superuser_token_headers, json={"name": name}
    )
    assert r.status_code == 409

    r = client.post(
        f"{API}/companies/",
        headers=s.admin.headers,
        json={"name": random_lower_string()},
    )
    assert r.status_code == 403


def test_read_company_members_only(client: TestClient, s: Setup) -> None:
    r = client.get(f"{API}/companies/{s.company.id}", headers=s.member.headers)
    assert r.status_code == 200
    r = client.get(f"{API}/companies/{s.company.id}", headers=s.other_admin.headers)
    assert r.status_code == 403


def test_company_optins_permissions(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    url = f"{API}/companies/{s.company.id}/jurisdictions"
    body = {"jurisdiction_ids": [str(s.allowed.id)]}

    assert client.put(url, headers=s.member.headers, json=body).status_code == 403
    assert client.put(url, headers=s.other_admin.headers, json=body).status_code == 403

    r = client.put(url, headers=s.admin.headers, json=body)
    assert r.status_code == 200
    assert _ids(r) == {str(s.allowed.id)}

    r = client.put(url, headers=superuser_token_headers, json=body)
    assert r.status_code == 200

    r = client.get(url, headers=s.member.headers)
    assert r.status_code == 200
    assert _ids(r) == {str(s.allowed.id)}
    assert client.get(url, headers=s.other_admin.headers).status_code == 403


def test_company_optins_reject_structural(client: TestClient, s: Setup) -> None:
    r = client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": [str(s.structural.id)]},
    )
    assert r.status_code == 422


def test_user_optins_limited_to_company_set(client: TestClient, s: Setup) -> None:
    client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": [str(s.allowed.id)]},
    )
    url = f"{API}/users/me/jurisdictions"

    r = client.put(
        url,
        headers=s.member.headers,
        json={"jurisdiction_ids": [str(s.not_allowed.id)]},
    )
    assert r.status_code == 403

    r = client.put(
        url, headers=s.member.headers, json={"jurisdiction_ids": [str(s.allowed.id)]}
    )
    assert r.status_code == 200
    assert _ids(r) == {str(s.allowed.id)}
    assert _ids(client.get(url, headers=s.member.headers)) == {str(s.allowed.id)}

    # Company drops the jurisdiction: the member's opt-in goes with it
    client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": []},
    )
    assert _ids(client.get(url, headers=s.member.headers)) == set()


def test_company_admin_manages_member_optins(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": [str(s.allowed.id)]},
    )
    url = f"{API}/users/{s.member.user.id}/jurisdictions"
    body = {"jurisdiction_ids": [str(s.allowed.id)]}

    r = client.put(url, headers=s.admin.headers, json=body)
    assert r.status_code == 200
    assert _ids(client.get(url, headers=s.admin.headers)) == {str(s.allowed.id)}
    assert client.get(url, headers=superuser_token_headers).status_code == 200

    assert client.get(url, headers=s.other_admin.headers).status_code == 403
    assert client.put(url, headers=s.other_admin.headers, json=body).status_code == 403
    admin_url = f"{API}/users/{s.admin.user.id}/jurisdictions"
    assert client.get(admin_url, headers=s.member.headers).status_code == 403


def test_user_public_includes_company(client: TestClient, s: Setup) -> None:
    r = client.get(f"{API}/users/me", headers=s.admin.headers)
    assert r.json()["company_id"] == str(s.company.id)
    assert r.json()["company_role"] == "admin"


def test_company_admins_visible_to_members(
    client: TestClient, db: Session, s: Setup
) -> None:
    inactive = _account(client, db, s.company, CompanyRole.admin)
    inactive.user.is_active = False
    db.add(inactive.user)
    db.commit()
    url = f"{API}/companies/{s.company.id}/admins"

    r = client.get(url, headers=s.member.headers)
    assert r.status_code == 200
    # Members and inactive admins are left out
    assert r.json()["data"] == [{"email": s.admin.user.email, "full_name": None}]
    assert client.get(url, headers=s.other_admin.headers).status_code == 403


def test_company_jurisdiction_user_counts(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": [str(s.allowed.id), str(s.not_allowed.id)]},
    )
    for account in (s.admin, s.member):
        client.put(
            f"{API}/users/me/jurisdictions",
            headers=account.headers,
            json={"jurisdiction_ids": [str(s.allowed.id)]},
        )
    url = f"{API}/companies/{s.company.id}/jurisdictions/user-counts"

    r = client.get(url, headers=s.admin.headers)
    assert r.status_code == 200
    # Opted in by the company but picked by no user: omitted
    assert r.json()["data"] == [{"jurisdiction_id": str(s.allowed.id), "user_count": 2}]
    assert client.get(url, headers=superuser_token_headers).status_code == 200

    assert client.get(url, headers=s.member.headers).status_code == 403
    assert client.get(url, headers=s.other_admin.headers).status_code == 403


def test_company_jurisdiction_affected_users(
    client: TestClient, superuser_token_headers: dict[str, str], s: Setup
) -> None:
    ids = [str(s.allowed.id), str(s.not_allowed.id)]
    client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": ids},
    )
    client.put(
        f"{API}/users/me/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": ids},
    )
    client.put(
        f"{API}/users/me/jurisdictions",
        headers=s.member.headers,
        json={"jurisdiction_ids": [str(s.allowed.id)]},
    )
    url = f"{API}/companies/{s.company.id}/jurisdictions/affected-users"

    r = client.post(url, headers=s.admin.headers, json={"jurisdiction_ids": ids})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert {(u["email"], u["jurisdiction_count"]) for u in body["data"]} == {
        (s.admin.user.email, 2),
        (s.member.user.email, 1),
    }

    r = client.post(url, headers=s.admin.headers, json={"jurisdiction_ids": [ids[1]]})
    assert [u["email"] for u in r.json()["data"]] == [s.admin.user.email]
    assert (
        client.post(
            url, headers=superuser_token_headers, json={"jurisdiction_ids": ids}
        ).status_code
        == 200
    )

    for account in (s.member, s.other_admin):
        r = client.post(url, headers=account.headers, json={"jurisdiction_ids": ids})
        assert r.status_code == 403


def test_jurisdiction_id_endpoints(client: TestClient, s: Setup) -> None:
    ids = [str(s.allowed.id), str(s.not_allowed.id)]
    client.put(
        f"{API}/companies/{s.company.id}/jurisdictions",
        headers=s.admin.headers,
        json={"jurisdiction_ids": ids},
    )
    client.put(
        f"{API}/users/me/jurisdictions",
        headers=s.member.headers,
        json={"jurisdiction_ids": [str(s.allowed.id)]},
    )

    company_url = f"{API}/companies/{s.company.id}/jurisdictions/ids"
    r = client.get(company_url, headers=s.member.headers)
    assert r.status_code == 200
    assert set(r.json()["jurisdiction_ids"]) == set(ids)
    assert r.json()["count"] == 2
    assert client.get(company_url, headers=s.other_admin.headers).status_code == 403

    r = client.get(f"{API}/users/me/jurisdictions/ids", headers=s.member.headers)
    assert r.json() == {"jurisdiction_ids": [str(s.allowed.id)], "count": 1}

    member_url = f"{API}/users/{s.member.user.id}/jurisdictions/ids"
    r = client.get(member_url, headers=s.admin.headers)
    assert r.json() == {"jurisdiction_ids": [str(s.allowed.id)], "count": 1}
    assert client.get(member_url, headers=s.other_admin.headers).status_code == 403
    admin_url = f"{API}/users/{s.admin.user.id}/jurisdictions/ids"
    assert client.get(admin_url, headers=s.member.headers).status_code == 403
