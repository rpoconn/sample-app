from datetime import UTC, datetime
from typing import Any

from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Generic message
class Message(SQLModel):
    message: str


# The body of every error response; see app.core.errors
class ErrorResponse(SQLModel):
    detail: str
    code: str
    context: dict[str, Any] = Field(default_factory=dict)
