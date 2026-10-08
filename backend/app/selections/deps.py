"""Resolve whose selection a route acts on, checking the caller may read or write it."""

import uuid
from typing import Annotated

from fastapi import Depends

from app.auth.deps import CurrentUser
from app.companies.deps import require_company_admin, require_company_member
from app.companies.models import Company
from app.core.deps import SessionDep
from app.core.errors import Forbidden, NotFound
from app.selections.service import SelectionOwner
from app.users.models import User


def my_owner(current_user: CurrentUser) -> SelectionOwner:
    return SelectionOwner.of_user(current_user)


def user_owner(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> SelectionOwner:
    """Superusers and admins of the user's company."""
    user = session.get(User, user_id)
    if not user:
        if not current_user.is_superuser:
            # Don't reveal whether the id exists to non-superusers
            raise Forbidden("The user doesn't have enough privileges")
        raise NotFound("User not found", code="user_not_found")
    require_company_admin(current_user, user.company_id)
    return SelectionOwner.of_user(user)


def _company_owner(session: SessionDep, company_id: uuid.UUID) -> SelectionOwner:
    if not session.get(Company, company_id):
        raise NotFound("Company not found", code="company_not_found")
    return SelectionOwner.of_company(company_id)


def company_reader(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> SelectionOwner:
    require_company_member(current_user, company_id)
    return _company_owner(session, company_id)


def company_writer(
    session: SessionDep, current_user: CurrentUser, company_id: uuid.UUID
) -> SelectionOwner:
    require_company_admin(current_user, company_id)
    return _company_owner(session, company_id)


MyOwner = Annotated[SelectionOwner, Depends(my_owner)]
UserOwner = Annotated[SelectionOwner, Depends(user_owner)]
CompanyReader = Annotated[SelectionOwner, Depends(company_reader)]
CompanyWriter = Annotated[SelectionOwner, Depends(company_writer)]
