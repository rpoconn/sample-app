import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Generic message
class Message(SQLModel):
    message: str


# The body of every error response; see app.errors
class ErrorResponse(SQLModel):
    detail: str
    code: str
    context: dict[str, Any] = Field(default_factory=dict)


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: uuid.UUID | None = None
    jti: uuid.UUID
    exp: datetime


# Access tokens revoked by logout; rows can be pruned once expires_at has passed
class RevokedToken(SQLModel, table=True):
    jti: uuid.UUID = Field(primary_key=True)
    expires_at: datetime = Field(index=True)
