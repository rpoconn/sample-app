import uuid
from typing import Any

from fastapi import APIRouter

from app import crud
from app.api.deps import SessionDep
from app.errors import Conflict, errors
from app.models import (
    CompanyRole,
    UserCreate,
    UserPublic,
    UserRegister,
)

router = APIRouter(tags=["private"], prefix="/private", responses=errors(422))


# UserCreate without is_superuser, so this route can't mint superusers
class PrivateUserCreate(UserRegister):
    # None places the user in the default company
    company_id: uuid.UUID | None = None
    company_role: CompanyRole = CompanyRole.admin


@router.post("/users", response_model=UserPublic, responses=errors(404, 409))
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user.
    """
    if crud.get_user_by_email(session=session, email=user_in.email):
        raise Conflict("User with this email already exists", code="email_taken")
    return crud.create_user(
        session=session, user_create=UserCreate.model_validate(user_in.model_dump())
    )
