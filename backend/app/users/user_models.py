import uuid
from datetime import datetime

from pydantic import EmailStr, field_validator
from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.companies.company_models import DEFAULT_COMPANY_ID, CompanyRole
from app.core.schemas import get_datetime_utc


def lower_email(email: str | None) -> str | None:
    """Emails are stored and looked up lowercased, so case never makes a new account."""
    return email.lower() if email else email


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)

    normalize_email = field_validator("email")(lower_email)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    # None places the user in the default company
    company_id: uuid.UUID | None = None
    company_role: CompanyRole = CompanyRole.admin


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    normalize_email = field_validator("email")(lower_email)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    company_id: uuid.UUID | None = None
    company_role: CompanyRole | None = None

    normalize_email = field_validator("email")(lower_email)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)

    normalize_email = field_validator("email")(lower_email)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    __table_args__ = (
        # Target for user_jurisdiction's (user_id, company_id) foreign key
        UniqueConstraint("id", "company_id", name="uq_user_id_company"),
        CheckConstraint(
            "company_role IN ('member', 'admin')", name="ck_user_company_role"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    company_id: uuid.UUID = Field(
        default=DEFAULT_COMPANY_ID,
        foreign_key="company.id",
        nullable=False,
        ondelete="RESTRICT",
        index=True,
    )
    company_role: CompanyRole = Field(default=CompanyRole.admin, sa_type=String(20))
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    # Bumped on every write to the user's opt-ins, cascades included
    jurisdictions_version: int = Field(
        default=0, sa_column_kwargs={"server_default": "0"}
    )
    # Bumped on password and email changes; tokens carrying an older one are rejected
    auth_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    company_id: uuid.UUID
    company_role: CompanyRole
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int
