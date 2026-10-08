from datetime import UTC, datetime, timedelta
from email.header import Header
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import col, delete

from app.auth.auth_deps import (
    CurrentUser,
    TokenPayloadDep,
    get_current_active_superuser,
)
from app.auth.auth_models import RevokedToken, Token
from app.auth.auth_service import (
    authenticate,
    generate_password_reset_token,
    verify_password_reset_token,
)
from app.companies.company_deps import is_company_active
from app.core import security
from app.core.config import settings
from app.core.deps import SessionDep
from app.core.errors import ApiError, NotFound, errors, json_errors
from app.core.schemas import Message
from app.mail.mail_service import generate_reset_password_email, send_email
from app.users import user_service as users
from app.users.user_models import NewPassword, UserPublic, UserUpdate

router = APIRouter(tags=["login"], responses=errors(422))


@router.post("/login/access-token", responses=errors(400))
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise ApiError("Incorrect email or password", code="invalid_grant")
    elif not user.is_active:
        raise ApiError("Inactive user", code="invalid_grant")
    elif not user.is_superuser and not is_company_active(session, user):
        raise ApiError("Company is inactive", code="invalid_grant")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/logout", responses=errors(401))
def logout(session: SessionDep, token_data: TokenPayloadDep) -> Message:
    """
    Revoke the current access token
    """
    # Expired tokens are rejected anyway, so their rows are no longer needed
    session.exec(
        delete(RevokedToken).where(col(RevokedToken.expires_at) < datetime.now(UTC))
    )
    session.add(RevokedToken(jti=token_data.jti, expires_at=token_data.exp))
    session.commit()
    return Message(message="Logged out")


@router.post("/login/test-token", response_model=UserPublic, responses=errors(401, 403))
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(
    email: str, session: SessionDep, background_tasks: BackgroundTasks
) -> Message:
    """
    Password Recovery
    """
    user = users.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists, and after the response so its
    # timing doesn't reveal that either
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        background_tasks.add_task(
            send_email,
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password", responses=errors(400))
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise ApiError("Invalid token", code="invalid_reset_token")
    user = users.get_user_by_email(session=session, email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise ApiError("Invalid token", code="invalid_reset_token")
    elif not user.is_active:
        raise ApiError("Inactive user", code="user_inactive")
    user_in_update = UserUpdate(password=body.new_password)
    users.update_user(
        session=session,
        db_user=user,
        user_in=user_in_update,
    )
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
    responses=json_errors(401, 403, 404, 422),
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = users.get_user_by_email(session=session, email=email)

    if not user:
        raise NotFound(
            "The user with this username does not exist in the system.",
            code="user_not_found",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content,
        headers={"X-Email-Subject": _header_value(email_data.subject)},
    )


def _header_value(text: str) -> str:
    """HTTP headers are latin-1, so RFC 2047-encode anything outside ASCII."""
    text = " ".join(text.splitlines())
    return text if text.isascii() else Header(text, "utf-8").encode()
