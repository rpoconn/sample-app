import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app import crud
from app.api.deps import SessionDep
from app.core.security import get_password_hash
from app.errors import Conflict, NotFound, errors
from app.models import (
    DEFAULT_COMPANY_ID,
    Company,
    CompanyRole,
    User,
    UserPublic,
)

router = APIRouter(tags=["private"], prefix="/private", responses=errors(422))


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False
    # None places the user in the default company
    company_id: uuid.UUID | None = None
    company_role: CompanyRole = CompanyRole.admin


@router.post("/users/", response_model=UserPublic, responses=errors(404, 409))
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user.
    """
    company_id = user_in.company_id or DEFAULT_COMPANY_ID
    if not session.get(Company, company_id):
        raise NotFound("Company not found", code="company_not_found")
    if crud.get_user_by_email(session=session, email=user_in.email):
        raise Conflict("User with this email already exists", code="email_taken")

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        company_id=company_id,
        company_role=user_in.company_role,
    )

    session.add(user)
    session.commit()

    return user
