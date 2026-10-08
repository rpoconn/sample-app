import uuid

from sqlmodel import Session, col, select

from app.companies.company_models import (
    DEFAULT_COMPANY_ID,
    Company,
    CompanyCreate,
    CompanyRole,
    CompanyUpdate,
)
from app.core.errors import Conflict, NotFound
from app.core.schemas import get_datetime_utc
from app.users.user_models import User


def get_company(*, session: Session, company_id: uuid.UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise NotFound("Company not found", code="company_not_found")
    return company


def ensure_default_company(*, session: Session, name: str) -> Company:
    company = session.get(Company, DEFAULT_COMPANY_ID)
    if not company:
        company = Company(id=DEFAULT_COMPANY_ID, name=name)
        session.add(company)
        session.commit()
        session.refresh(company)
    return company


def _check_company_name(
    *, session: Session, name: str, exclude_id: uuid.UUID | None
) -> None:
    statement = select(Company.id).where(Company.name == name)
    if exclude_id:
        statement = statement.where(Company.id != exclude_id)
    if session.exec(statement).first():
        raise Conflict(
            "A company with this name already exists", code="company_name_taken"
        )


def create_company(*, session: Session, company_in: CompanyCreate) -> Company:
    _check_company_name(session=session, name=company_in.name, exclude_id=None)
    db_obj = Company.model_validate(company_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_company(
    *, session: Session, db_obj: Company, company_in: CompanyUpdate
) -> Company:
    data = company_in.model_dump(exclude_unset=True, exclude_none=True)
    if db_obj.id == DEFAULT_COMPANY_ID and data.get("is_active") is False:
        raise Conflict(
            "The default company can't be deactivated",
            code="cannot_deactivate_default_company",
        )
    if "name" in data:
        _check_company_name(session=session, name=data["name"], exclude_id=db_obj.id)
    db_obj.sqlmodel_update(data, update={"updated_at": get_datetime_utc()})
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_company_admins(*, session: Session, company_id: uuid.UUID) -> list[User]:
    """Active admins of the company, for members who need one to change a setting."""
    statement = (
        select(User)
        .where(
            User.company_id == company_id,
            User.company_role == CompanyRole.admin,
            col(User.is_active),
        )
        .order_by(col(User.email))
    )
    return list(session.exec(statement).all())
