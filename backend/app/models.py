import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import EmailStr
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Seeded by migration; users created without a company_id are placed here
DEFAULT_COMPANY_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


class CompanyRole(StrEnum):
    member = "member"
    admin = "admin"


# Disambiguates codes that repeat across levels, e.g. "CA" is Canada or California
class RegionType(StrEnum):
    country = "country"
    subdivision = "subdivision"
    city = "city"


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
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    updated_at: datetime | None = Field(default_factory=get_datetime_utc)


# Properties to return via API, id is always required
class CompanyPublic(CompanyBase):
    id: uuid.UUID
    created_at: datetime | None = None


class CompaniesPublic(SQLModel):
    data: list[CompanyPublic]
    count: int


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


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


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    company_id: uuid.UUID | None = None
    company_role: CompanyRole | None = None


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
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
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    company_id: uuid.UUID
    company_role: CompanyRole
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Who members can contact to change company settings; only what's needed to reach them
class CompanyAdmin(SQLModel):
    email: EmailStr
    full_name: str | None = None


class CompanyAdmins(SQLModel):
    data: list[CompanyAdmin]


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
    # ISO 3166-1 alpha-2 for countries, ISO 3166-2 suffix for subdivisions
    # (e.g. "WA" for US-WA), UN/LOCODE location for cities (e.g. "LAX")
    code: str | None = Field(default=None, min_length=1, max_length=3)
    region_type: RegionType | None = Field(default=None, sa_type=String(20))


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


# Properties to receive via API on creation
class JurisdictionCreate(JurisdictionBase):
    parent_id: uuid.UUID | None = None
    # None appends after the last sibling
    sort_order: int | None = Field(default=None, ge=0)


# Properties to receive via API on update, all are optional.
# parent_id is only applied when sent, so an explicit null moves the node to the root
class JurisdictionUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_structural: bool | None = None
    code: str | None = Field(default=None, min_length=1, max_length=3)
    region_type: RegionType | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int | None = Field(default=None, ge=0)


# A company's opt-in to a jurisdiction; users of the company may only pick from these
class CompanyJurisdiction(SQLModel, table=True):
    company_id: uuid.UUID = Field(
        foreign_key="company.id", primary_key=True, ondelete="CASCADE"
    )
    # RESTRICT so deleting a jurisdiction never silently drops customer opt-ins
    jurisdiction_id: uuid.UUID = Field(
        foreign_key="jurisdiction.id", primary_key=True, ondelete="RESTRICT", index=True
    )
    created_at: datetime | None = Field(default_factory=get_datetime_utc)


# A user's opt-in to a jurisdiction. The two composite foreign keys let the database
# enforce that the user's company has opted into the jurisdiction, and removing the
# company opt-in cascades to every user opt-in for it.
class UserJurisdiction(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "company_id"],
            ["user.id", "user.company_id"],
            name="fk_userjurisdiction_user_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "jurisdiction_id"],
            ["companyjurisdiction.company_id", "companyjurisdiction.jurisdiction_id"],
            name="fk_userjurisdiction_company_optin",
            ondelete="CASCADE",
        ),
        Index(
            "ix_userjurisdiction_company_jurisdiction", "company_id", "jurisdiction_id"
        ),
    )

    user_id: uuid.UUID = Field(primary_key=True)
    jurisdiction_id: uuid.UUID = Field(primary_key=True)
    company_id: uuid.UUID
    created_at: datetime | None = Field(default_factory=get_datetime_utc)


# How many of a company's users have opted into a jurisdiction
class JurisdictionUserCount(SQLModel):
    jurisdiction_id: uuid.UUID
    user_count: int


class JurisdictionUserCounts(SQLModel):
    data: list[JurisdictionUserCount]


# A company user who has opted into some of a given set of jurisdictions
class JurisdictionAffectedUser(SQLModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    # How many of the given jurisdictions this user has selected
    jurisdiction_count: int


class JurisdictionAffectedUsers(SQLModel):
    data: list[JurisdictionAffectedUser]
    count: int


# Just the selected ids, for callers that don't need the full jurisdictions
class JurisdictionIds(SQLModel):
    jurisdiction_ids: list[uuid.UUID]
    count: int


# Full set of jurisdiction ids to opt into; replaces the existing set
class JurisdictionSelection(SQLModel):
    jurisdiction_ids: list[uuid.UUID]


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
    jti: uuid.UUID
    exp: datetime


# Access tokens revoked by logout; rows can be pruned once expires_at has passed
class RevokedToken(SQLModel, table=True):
    jti: uuid.UUID = Field(primary_key=True)
    expires_at: datetime = Field(index=True)


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
