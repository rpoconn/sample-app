import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, func, select

from app.auth.auth_deps import CurrentUser, get_current_active_superuser
from app.auth.auth_models import Token
from app.auth.auth_service import issue_token
from app.core.config import settings
from app.core.deps import SessionDep
from app.core.errors import ApiError, Conflict, Forbidden, NotFound, errors
from app.core.schemas import Message
from app.core.security import verify_password
from app.mail.mail_service import generate_new_account_email, send_email
from app.users import user_service
from app.users.user_models import (
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

router = APIRouter(prefix="/users", tags=["users"], responses=errors(401, 403, 422))


@router.get(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
    users = session.exec(statement).all()

    users_public = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_public, count=count)


@router.post(
    "",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    responses=errors(404, 409),
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = user_service.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise Conflict(
            "The user with this email already exists in the system.",
            code="email_taken",
        )

    user = user_service.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic, responses=errors(409))
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = user_service.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != current_user.id:
            raise Conflict("User with this email already exists", code="email_taken")
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    return user_service.save_user(session=session, user=current_user)


@router.patch("/me/password", responses=errors(400))
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Token:
    """
    Update own password. This revokes every existing token, the caller's
    included, so the response carries a new one.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise ApiError("Incorrect password", code="incorrect_password")
    if body.current_password == body.new_password:
        raise ApiError(
            "New password cannot be the same as the current one",
            code="password_unchanged",
        )
    user = user_service.update_user(
        session=session,
        db_user=current_user,
        user_in=UserUpdate(password=body.new_password),
    )
    return issue_token(user)


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message, responses=errors(409))
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise Conflict(
            "Super users are not allowed to delete themselves",
            code="cannot_delete_self",
        )
    user_service.delete_user(session=session, db_user=current_user)
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic, responses=errors(409))
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = user_service.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise Conflict(
            "The user with this email already exists in the system",
            code="email_taken",
        )
    user_create = UserCreate.model_validate(user_in)
    user = user_service.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic, responses=errors(404))
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise Forbidden("The user doesn't have enough privileges")
    if user is None:
        raise NotFound("User not found", code="user_not_found")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    responses=errors(404, 409),
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise NotFound(
            "The user with this id does not exist in the system",
            code="user_not_found",
        )
    if user_in.email:
        existing_user = user_service.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != user_id:
            raise Conflict("User with this email already exists", code="email_taken")

    db_user = user_service.update_user(
        session=session, db_user=db_user, user_in=user_in
    )
    return db_user


@router.delete(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    responses=errors(404, 409),
)
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise NotFound("User not found", code="user_not_found")
    if user == current_user:
        raise Conflict(
            "Super users are not allowed to delete themselves",
            code="cannot_delete_self",
        )
    user_service.delete_user(session=session, db_user=user)
    return Message(message="User deleted successfully")
