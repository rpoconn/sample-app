import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Shared properties
class JurisdictionBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, index=True)
    is_structural: bool = False


# Database model: adjacency list (parent_id) + materialized path for tree queries
class Jurisdiction(JurisdictionBase, table=True):
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_jurisdiction_parent_name"),
        # SQLite treats NULL parent_ids as distinct, so enforce unique root names separately
        Index(
            "ix_jurisdiction_root_name",
            "name",
            unique=True,
            sqlite_where=text("parent_id IS NULL"),
        ),
        Index("ix_jurisdiction_parent_sort", "parent_id", "sort_order"),
        CheckConstraint("depth >= 0", name="ck_jurisdiction_depth"),
        CheckConstraint("sort_order >= 0", name="ck_jurisdiction_sort_order"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    parent_id: uuid.UUID | None = Field(
        default=None, foreign_key="jurisdiction.id", ondelete="RESTRICT"
    )
    # Position among siblings, preserves source ordering
    sort_order: int = 0
    # Root = 0
    depth: int = 0
    # Ancestor-or-self ids as hex, e.g. "/<root>/<child>/"; used for subtree prefix queries
    path: str = Field(max_length=1024, unique=True, index=True)
    # Display breadcrumb, e.g. "United States / States / California"
    name_path: str = Field(max_length=2048)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    updated_at: datetime | None = Field(default_factory=get_datetime_utc)


# Properties to return via API, id is always required
class JurisdictionPublic(JurisdictionBase):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    sort_order: int
    depth: int
    path: str
    name_path: str
    child_count: int = 0


class JurisdictionsPublic(SQLModel):
    data: list[JurisdictionPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: uuid.UUID | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
