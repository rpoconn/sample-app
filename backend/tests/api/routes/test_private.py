import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import CompanyCreate, CompanyRole, User
from tests.utils.utils import random_email, random_lower_string


def test_create_user(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/private/users/",
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
    company = crud.create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    r = client.post(
        f"{settings.API_V1_STR}/private/users/",
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
        f"{settings.API_V1_STR}/private/users/",
        json={
            "email": random_email(),
            "password": "password123",
            "full_name": "Nobody",
            "company_id": str(uuid.uuid4()),
        },
    )

    assert r.status_code == 404
