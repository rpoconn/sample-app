"""Builders for test data, and the accounts the route tests act as."""

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.companies.company_models import Company, CompanyCreate, CompanyRole
from app.companies.company_service import create_company
from app.jurisdictions.jurisdiction_models import Jurisdiction, JurisdictionCreate
from app.jurisdictions.jurisdiction_service import create_jurisdiction
from app.users.user_models import User, UserCreate
from app.users.user_service import create_user
from tests.utils.user import user_authentication_headers
from tests.utils.utils import random_email, random_lower_string


@dataclass
class Account:
    user: User
    headers: dict[str, str]
    password: str


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


def make_company(db: Session) -> Company:
    return create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )


def make_user(db: Session, company: Company) -> User:
    user_in = UserCreate(
        email=random_email(), password=random_lower_string(), company_id=company.id
    )
    return create_user(session=db, user_create=user_in)


def make_account(
    client: TestClient,
    db: Session,
    company: Company,
    role: CompanyRole,
    *,
    superuser: bool = False,
) -> Account:
    email, password = random_email(), random_lower_string()
    user = create_user(
        session=db,
        user_create=UserCreate(
            email=email,
            password=password,
            company_id=company.id,
            company_role=role,
            is_superuser=superuser,
        ),
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    return Account(user, headers, password)


def make_jurisdiction(
    db: Session, parent: Jurisdiction | None = None, *, structural: bool = False
) -> Jurisdiction:
    return create_jurisdiction(
        session=db,
        jurisdiction_in=JurisdictionCreate(
            name=random_lower_string(),
            parent_id=parent.id if parent else None,
            is_structural=structural,
        ),
    )
