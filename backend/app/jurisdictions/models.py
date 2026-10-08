import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from app.core.schemas import get_datetime_utc


# Disambiguates codes that repeat across levels, e.g. "CA" is Canada or California
class RegionType(StrEnum):
    country = "country"
    subdivision = "subdivision"
    city = "city"


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


# Properties to return via API, id is always required. Storage columns (path, depth,
# sort_order) stay internal: lists return siblings in display order instead.
class JurisdictionPublic(JurisdictionBase):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name_path: str
    child_count: int = 0


class JurisdictionsPublic(SQLModel):
    """Unpaginated: `count` is the total, so it always equals `len(data)`."""

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
    # Moving a subtree that companies hold licenses in is refused unless this is set
    allow_licensed_move: bool = False
