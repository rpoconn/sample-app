"""Invariants a user change must keep: every active company keeps an active admin,
and the system keeps an active superuser. A delete is checked as
`after={"is_active": False}`."""

from typing import Any

from sqlmodel import Session, col, select

from app.companies.company_models import Company, CompanyRole
from app.core.errors import Conflict
from app.users.user_models import User


def ensure_company_keeps_admin(
    *, session: Session, user: User, after: dict[str, Any]
) -> None:
    """Raise if `after` (the user's new field values) leaves the user's current
    company without an active admin while it still has other active users."""
    if not (user.is_active and user.company_role == CompanyRole.admin):
        return
    stays_admin = (
        after.get("is_active", True)
        and after.get("company_role", user.company_role) == CompanyRole.admin
        and after.get("company_id", user.company_id) == user.company_id
    )
    if stays_admin:
        return
    company = session.get(Company, user.company_id)
    if not company or not company.is_active:
        return
    others = select(User.company_role).where(
        User.company_id == user.company_id,
        col(User.is_active).is_(True),
        User.id != user.id,
    )
    roles = set(session.exec(others).all())
    if roles and CompanyRole.admin not in roles:
        raise Conflict(
            "The company would be left without an active admin; promote another user first",
            code="last_company_admin",
            context={"company_id": str(user.company_id)},
        )


def ensure_keeps_superuser(
    *, session: Session, user: User, after: dict[str, Any]
) -> None:
    """Raise if `after` removes the last active superuser."""
    if not (user.is_active and user.is_superuser):
        return
    if after.get("is_active", True) and after.get("is_superuser", True):
        return
    other = select(User.id).where(
        col(User.is_superuser).is_(True),
        col(User.is_active).is_(True),
        User.id != user.id,
    )
    if not session.exec(other).first():
        raise Conflict("This is the last active superuser", code="last_superuser")
