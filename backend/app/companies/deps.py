import uuid

from sqlmodel import Session

from app.companies.models import Company, CompanyRole
from app.core.errors import Forbidden
from app.users.models import User


def is_company_active(session: Session, user: User) -> bool:
    company = session.get(Company, user.company_id)
    return company is not None and company.is_active


def require_company_member(current_user: User, company_id: uuid.UUID) -> None:
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise Forbidden("The user doesn't have enough privileges")


def require_company_admin(current_user: User, company_id: uuid.UUID) -> None:
    is_admin = (
        current_user.company_id == company_id
        and current_user.company_role == CompanyRole.admin
    )
    if not current_user.is_superuser and not is_admin:
        raise Forbidden("The user doesn't have enough privileges")
