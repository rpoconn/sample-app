import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import CompanyRole, RevokedToken, TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_token_payload(session: SessionDep, token: TokenDep) -> TokenPayload:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if session.get(RevokedToken, token_data.jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return token_data


TokenPayloadDep = Annotated[TokenPayload, Depends(get_token_payload)]


def get_current_user(session: SessionDep, token_data: TokenPayloadDep) -> User:
    user = session.get(User, token_data.sub)
    if not user:
        # 401 (not 404) so clients drop stale tokens, e.g. after a DB reset
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def require_company_member(current_user: User, company_id: uuid.UUID) -> None:
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )


def require_company_admin(current_user: User, company_id: uuid.UUID) -> None:
    is_admin = (
        current_user.company_id == company_id
        and current_user.company_role == CompanyRole.admin
    )
    if not current_user.is_superuser and not is_admin:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
