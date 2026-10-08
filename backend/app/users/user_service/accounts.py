from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, func, select

from app.companies.company_models import DEFAULT_COMPANY_ID, CompanyRole
from app.companies.company_service import get_company
from app.core.errors import Conflict
from app.core.security import get_password_hash
from app.selections.selection_models import UserJurisdiction
from app.selections.selection_service.versions import bump_user_versions
from app.users.user_models import User, UserCreate, UserUpdate
from app.users.user_service.guards import (
    ensure_company_keeps_admin,
    ensure_keeps_superuser,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    company_id = user_create.company_id or DEFAULT_COMPANY_ID
    get_company(session=session, company_id=company_id)
    db_obj = User.model_validate(
        user_create,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "company_id": company_id,
        },
    )
    return save_user(session=session, user=db_obj)


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    # Company membership can be changed but never cleared
    for key in ("company_id", "company_role"):
        if key in user_data and user_data[key] is None:
            del user_data[key]
    new_company_id = user_data.get("company_id")
    moving = new_company_id is not None and new_company_id != db_user.company_id
    if moving:
        get_company(session=session, company_id=user_data["company_id"])
        # Admin rights don't carry across tenants
        user_data.setdefault("company_role", CompanyRole.member)
    ensure_company_keeps_admin(session=session, user=db_user, after=user_data)
    ensure_keeps_superuser(session=session, user=db_user, after=user_data)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    if moving:
        # Opt-ins belong to the old company; the FK rejects the move while they exist
        session.exec(
            delete(UserJurisdiction).where(col(UserJurisdiction.user_id) == db_user.id)
        )
        bump_user_versions(session=session, user_ids=[db_user.id])
    db_user.sqlmodel_update(user_data, update=extra_data)
    return save_user(session=session, user=db_user)


def save_user(*, session: Session, user: User) -> User:
    """Commit the user. The callers check the email first, but a concurrent write
    can still take it, and the unique index then answers 409, not 500."""
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise Conflict("User with this email already exists", code="email_taken")
    session.refresh(user)
    return user


def delete_user(*, session: Session, db_user: User) -> None:
    gone = {"is_active": False}
    ensure_company_keeps_admin(session=session, user=db_user, after=gone)
    ensure_keeps_superuser(session=session, user=db_user, after=gone)
    session.delete(db_user)
    session.commit()


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(func.lower(User.email) == email.lower())
    session_user = session.exec(statement).first()
    return session_user
