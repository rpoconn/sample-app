import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
    require_company_admin,
)
from app.api.routes.jurisdictions import to_public_list
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.errors import ApiError, Conflict, Forbidden, NotFound
from app.models import (
    JurisdictionIds,
    JurisdictionSelection,
    JurisdictionsPublic,
    JurisdictionSubtreeToggle,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
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
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise Conflict(
            "The user with this email already exists in the system.",
            code="email_taken",
        )

    user = crud.create_user(session=session, user_create=user_in)
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


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise Conflict("User with this email already exists", code="email_taken")
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise ApiError("Incorrect password", code="incorrect_password")
    if body.current_password == body.new_password:
        raise ApiError(
            "New password cannot be the same as the current one",
            code="password_unchanged",
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.get("/me/jurisdictions", response_model=JurisdictionsPublic)
def read_my_jurisdictions(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Get the jurisdictions the current user has opted into.
    """
    rows = crud.get_user_jurisdictions(session=session, user_id=current_user.id)
    return to_public_list(session, rows)


@router.get("/me/jurisdictions/ids", response_model=JurisdictionIds)
def read_my_jurisdiction_ids(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Ids of the jurisdictions the current user has opted into.
    """
    rows = crud.get_user_jurisdictions(session=session, user_id=current_user.id)
    return JurisdictionIds(jurisdiction_ids=[j.id for j in rows], count=len(rows))


@router.put("/me/jurisdictions", response_model=JurisdictionsPublic)
def set_my_jurisdictions(
    *, session: SessionDep, current_user: CurrentUser, body: JurisdictionSelection
) -> Any:
    """
    Replace the current user's opt-ins; each must be opted into by their company.
    """
    rows = crud.set_user_jurisdictions(
        session=session, user=current_user, jurisdiction_ids=body.jurisdiction_ids
    )
    return to_public_list(session, rows)


@router.post("/me/jurisdictions/subtree", response_model=JurisdictionIds)
def toggle_my_jurisdiction_subtree(
    *, session: SessionDep, current_user: CurrentUser, body: JurisdictionSubtreeToggle
) -> Any:
    """
    Turn a jurisdiction and everything under it on or off for the current user,
    skipping any their company hasn't opted into.
    """
    rows = crud.toggle_user_subtree(
        session=session, user=current_user, root_id=body.root_id, enabled=body.enabled
    )
    return JurisdictionIds(jurisdiction_ids=[j.id for j in rows], count=len(rows))


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise Conflict(
            "Super users are not allowed to delete themselves",
            code="cannot_delete_self",
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise Conflict(
            "The user with this email already exists in the system",
            code="email_taken",
        )
    user_create = UserCreate.model_validate(user_in)
    user = crud.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic)
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
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise Conflict("User with this email already exists", code="email_taken")

    db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
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
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")


def _get_user_for_company_admin(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> User:
    user = session.get(User, user_id)
    if not user:
        if not current_user.is_superuser:
            # Don't reveal whether the id exists to non-superusers
            raise Forbidden("The user doesn't have enough privileges")
        raise NotFound("User not found", code="user_not_found")
    require_company_admin(current_user, user.company_id)
    return user


@router.get("/{user_id}/jurisdictions", response_model=JurisdictionsPublic)
def read_user_jurisdictions(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Any:
    """
    Get a user's opt-ins. Allowed for superusers and admins of the user's company.
    """
    user = _get_user_for_company_admin(session, current_user, user_id)
    rows = crud.get_user_jurisdictions(session=session, user_id=user.id)
    return to_public_list(session, rows)


@router.get("/{user_id}/jurisdictions/ids", response_model=JurisdictionIds)
def read_user_jurisdiction_ids(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Any:
    """
    Ids of a user's opt-ins. Allowed for superusers and admins of the user's company.
    """
    user = _get_user_for_company_admin(session, current_user, user_id)
    rows = crud.get_user_jurisdictions(session=session, user_id=user.id)
    return JurisdictionIds(jurisdiction_ids=[j.id for j in rows], count=len(rows))


@router.put("/{user_id}/jurisdictions", response_model=JurisdictionsPublic)
def set_user_jurisdictions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    body: JurisdictionSelection,
) -> Any:
    """
    Replace a user's opt-ins. Allowed for superusers and admins of the user's company.
    """
    user = _get_user_for_company_admin(session, current_user, user_id)
    rows = crud.set_user_jurisdictions(
        session=session, user=user, jurisdiction_ids=body.jurisdiction_ids
    )
    return to_public_list(session, rows)
