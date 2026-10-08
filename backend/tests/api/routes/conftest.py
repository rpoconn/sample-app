from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.companies.models import Company, CompanyCreate, CompanyRole
from app.companies.service import create_company
from app.jurisdictions.models import Jurisdiction, JurisdictionCreate
from app.jurisdictions.service import create_jurisdiction
from app.users.models import User, UserCreate
from app.users.service import create_user
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


@pytest.fixture
def s(client: TestClient, db: Session) -> Setup:
    """A company with an admin and a member, another company with its own admin, and
    three fresh root jurisdictions."""
    company = create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    other = create_company(
        session=db, company_in=CompanyCreate(name=random_lower_string())
    )
    return Setup(
        company=company,
        other_company=other,
        admin=make_account(client, db, company, CompanyRole.admin),
        member=make_account(client, db, company, CompanyRole.member),
        other_admin=make_account(client, db, other, CompanyRole.admin),
        allowed=make_jurisdiction(db),
        not_allowed=make_jurisdiction(db),
        structural=make_jurisdiction(db, structural=True),
    )
