import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.companies.models import CompanyCreate, CompanyRole
from app.companies.service import create_company
from app.core.config import settings
from app.users.models import User
from tests.utils.utils import assert_error, random_email, random_lower_string


def test_create_user(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/private/users",
        json={
            "email": "pollo@listo.com",
            "password": "password123",
            "full_name": "Pollo Listo",
        },
    )

    assert r.status_code == 200

    data = r.json()

    user = db.exec(select(User).where(User.id == uuid.UUID(data["id"]))).first()

    assert user
    assert user.email == "pollo@listo.com"
    assert user.full_name == "Pollo Listo"


def test_create_user_in_company(client: TestClient, db: Session) -> None:
    company = create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    r = client.post(
        f"{settings.API_V1_STR}/private/users",
        json={
            "email": random_email(),
            "password": "password123",
            "full_name": "Member",
            "company_id": str(company.id),
            "company_role": "member",
        },
    )

    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == str(company.id)
    assert data["company_role"] == CompanyRole.member


def test_create_user_unknown_company(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/private/users",
        json={
            "email": random_email(),
            "password": "password123",
            "full_name": "Nobody",
            "company_id": str(uuid.uuid4()),
        },
    )

    assert_error(r, 404, "company_not_found")


def test_create_user_existing_email(client: TestClient) -> None:
    body = {
        "email": random_email(),
        "password": "password123",
        "full_name": "Twice",
    }
    url = f"{settings.API_V1_STR}/private/users"
    assert client.post(url, json=body).status_code == 200

    r = client.post(url, json=body)
    assert_error(r, 409, "email_taken")


def test_create_user_ignores_superuser(client: TestClient) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/private/users",
        json={
            "email": random_email(),
            "password": "password123",
            "is_superuser": True,
        },
    )

    assert r.status_code == 200
    assert r.json()["is_superuser"] is False
