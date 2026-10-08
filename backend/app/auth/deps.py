import secrets
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.auth.models import RevokedToken, TokenPayload
from app.companies.deps import is_company_active
from app.core import security
from app.core.config import settings
from app.core.deps import SessionDep
from app.core.errors import Forbidden, Unauthorized
from app.users.models import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_token_payload(session: SessionDep, token: TokenDep) -> TokenPayload:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise Unauthorized("Could not validate credentials", code="invalid_token")
    if session.get(RevokedToken, token_data.jti):
        raise Unauthorized("Token has been revoked", code="token_revoked")
    return token_data


TokenPayloadDep = Annotated[TokenPayload, Depends(get_token_payload)]


def get_current_user(session: SessionDep, token_data: TokenPayloadDep) -> User:
    user = session.get(User, token_data.sub)
    if not user:
        # 401 (not 404) so clients drop stale tokens, e.g. after a DB reset
        raise Unauthorized("User not found", code="invalid_token")
    if not user.is_active:
        raise Forbidden("Inactive user", code="user_inactive")
    if not user.is_superuser and not is_company_active(session, user):
        raise Forbidden("Company is inactive", code="company_inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise Forbidden("The user doesn't have enough privileges")
    return current_user


service_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)
optional_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)


def require_service_caller(
    session: SessionDep,
    api_key: Annotated[str | None, Depends(service_api_key)],
    token: Annotated[str | None, Depends(optional_oauth2)],
) -> None:
    """Let in another service holding SERVICE_API_KEY, or a superuser's bearer token."""
    if api_key is not None:
        expected = settings.SERVICE_API_KEY
        if not expected or not secrets.compare_digest(api_key, expected):
            raise Unauthorized("Invalid API key", code="invalid_api_key")
        return
    if token is None:
        raise Unauthorized("Not authenticated")
    user = get_current_user(session, get_token_payload(session, token))
    get_current_active_superuser(user)
