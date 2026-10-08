import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: uuid.UUID | None = None
    jti: uuid.UUID
    exp: datetime
    ver: int = 0


# Access tokens revoked by logout; rows can be pruned once expires_at has passed
class RevokedToken(SQLModel, table=True):
    jti: uuid.UUID = Field(primary_key=True)
    expires_at: datetime = Field(index=True)
