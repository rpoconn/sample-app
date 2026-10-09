import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.auth.auth_deps import require_service_caller
from app.companies.company_models import Company
from app.core.deps import SessionDep
from app.core.errors import NotFound, errors
from app.jurisdictions.jurisdiction_models import Jurisdiction
from app.selections import selection_service as selections
from app.selections.selection_models import UserJurisdiction
from app.users.user_models import User

# Machine-to-machine reads for other services: X-API-Key or a superuser bearer token.
# Every route is scoped to one company; a user outside it is reported as not found.
router = APIRouter(
    prefix="/service/companies/{company_id}",
    tags=["service"],
    dependencies=[Depends(require_service_caller)],
    responses=errors(401, 403, 404, 422),
)


def get_company(session: Session, company_id: uuid.UUID) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise NotFound("Company not found", code="company_not_found")
    return company


def get_company_user(session: Session, company: Company, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if not user or user.company_id != company.id:
        raise NotFound("User not found", code="user_not_found")
    return user


def check_jurisdiction(session: Session, jurisdiction_id: uuid.UUID) -> None:
    if not session.get(Jurisdiction, jurisdiction_id):
        raise NotFound("Jurisdiction not found", code="jurisdiction_not_found")


@router.get("/users/{user_id}/jurisdiction-ids")
def read_user_jurisdiction_ids_for_service(
    session: SessionDep, company_id: uuid.UUID, user_id: uuid.UUID
) -> list[uuid.UUID]:
    """
    The user's active jurisdiction ids as a plain JSON array, e.g. ["…", "…"].

    An inactive user, or a user of an inactive company, monitors nothing: the
    response is [] rather than an error.
    """
    company = get_company(session, company_id)
    user = get_company_user(session, company, user_id)
    if not user.is_active or not company.is_active:
        return []
    owner = selections.SelectionOwner.of_user(user)
    return selections.get_selection(session=session, owner=owner).jurisdiction_ids


@router.get("/users/{user_id}/jurisdictions/{jurisdiction_id}/active")
def read_user_jurisdiction_active_for_service(
    session: SessionDep,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    jurisdiction_id: uuid.UUID,
) -> bool:
    """
    Whether one jurisdiction is active for the user, as a bare JSON true or false.

    Same rules as the id list: an inactive user, or a user of an inactive company,
    gets false.
    """
    company = get_company(session, company_id)
    user = get_company_user(session, company, user_id)
    check_jurisdiction(session, jurisdiction_id)
    if not user.is_active or not company.is_active:
        return False
    statement = select(UserJurisdiction.jurisdiction_id).where(
        UserJurisdiction.user_id == user.id,
        UserJurisdiction.jurisdiction_id == jurisdiction_id,
    )
    return session.exec(statement).first() is not None


@router.get("/jurisdictions/{jurisdiction_id}/user-ids")
def read_jurisdiction_user_ids_for_service(
    session: SessionDep, company_id: uuid.UUID, jurisdiction_id: uuid.UUID
) -> list[uuid.UUID]:
    """
    Ids of the company's active users who have this jurisdiction active, as a plain
    JSON array ordered by email. An inactive company has none: the response is [].
    """
    company = get_company(session, company_id)
    check_jurisdiction(session, jurisdiction_id)
    if not company.is_active:
        return []
    statement = (
        select(User.id)
        .join(UserJurisdiction, col(UserJurisdiction.user_id) == User.id)
        .where(
            UserJurisdiction.company_id == company.id,
            UserJurisdiction.jurisdiction_id == jurisdiction_id,
            col(User.is_active),
        )
        .order_by(col(User.email))
    )
    return list(session.exec(statement).all())
