import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from app.core.schemas import get_datetime_utc

# Seeded by migration; users created without a company_id are placed here
DEFAULT_COMPANY_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


class CompanyRole(StrEnum):
    member = "member"
    admin = "admin"


# Shared properties
class CompanyBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, unique=True, index=True)
    is_active: bool = True


# Properties to receive via API on creation
class CompanyCreate(CompanyBase):
    pass


# Properties to receive via API on update, all are optional
class CompanyUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


# Database model, database table inferred from class name
class Company(CompanyBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Bumped on every write to the company's opt-ins; the ETag of its selection
    jurisdictions_version: int = Field(
        default=0, sa_column_kwargs={"server_default": "0"}
    )
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    updated_at: datetime | None = Field(default_factory=get_datetime_utc)


# Properties to return via API, id is always required
class CompanyPublic(CompanyBase):
    id: uuid.UUID
    created_at: datetime | None = None


class CompaniesPublic(SQLModel):
    data: list[CompanyPublic]
    count: int


# Who members can contact to change company settings; only what's needed to reach them
class CompanyAdmin(SQLModel):
    email: EmailStr
    full_name: str | None = None


class CompanyAdmins(SQLModel):
    data: list[CompanyAdmin]
    count: int
