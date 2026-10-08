import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import EmailStr
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel

from app.models.models import get_datetime_utc


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


# Full set of jurisdiction ids to opt into; replaces the existing set
class JurisdictionSelection(SQLModel):
    jurisdiction_ids: list[uuid.UUID]


# A company's or user's opt-ins. version is also sent as the ETag; pass it back as
# If-Match so a write only lands on the selection it was based on.
class JurisdictionSelectionOut(SQLModel):
    jurisdiction_ids: list[uuid.UUID]
    count: int
    version: int


# Applied in order: add, add_subtrees, remove, remove_subtrees. A subtree is every
# selectable jurisdiction under the root, itself included. Ids in both add and remove
# (or in both subtree lists) are rejected.
class SelectionChange(SQLModel):
    add: list[uuid.UUID] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)
    add_subtrees: list[uuid.UUID] = Field(default_factory=list)
    remove_subtrees: list[uuid.UUID] = Field(default_factory=list)


# What a change to the company's opt-ins would do; nothing is written
class SelectionPreview(SQLModel):
    # Pass back as If-Match to commit exactly this preview
    version: int
    added: list[uuid.UUID]
    removed: list[uuid.UUID]
    # Users who would lose an opt-in
    affected_users: JurisdictionAffectedUsers


TreeSortBy = Literal["name", "enabled"]
SortDir = Literal["asc", "desc"]
# Whose opt-ins count as enabled: the company's or the current user's
SelectionScope = Literal["company", "user"]
# Whether a row is on in the current scope. Available (user scope only) is off but
# licensed by the company; disabled is off and unlicensed, so it can't be turned on.
StatusFilter = Literal["all", "enabled", "available", "disabled"]


# Across region types picks combine with AND, within a type with OR. A row passes a
# type when it or an ancestor is picked, so picking a country keeps its whole subtree.
class JurisdictionFilters(SQLModel):
    search: str = Field(default="", max_length=255)
    by_type: dict[RegionType, list[uuid.UUID]] = Field(default_factory=dict)
    status: StatusFilter = "all"


class JurisdictionFacetsQuery(SQLModel):
    scope: SelectionScope = "company"
    filters: JurisdictionFilters = Field(default_factory=JurisdictionFilters)


# A window of the grid's flattened rows; POST so filters and expansion fit
class JurisdictionRowsQuery(JurisdictionFacetsQuery):
    sort_by: TreeSortBy | None = None
    sort_dir: SortDir = "asc"
    # Rows opened in the view. None opens the roots, or when filtering, the
    # ancestors of every match.
    expanded_ids: list[uuid.UUID] | None = None
    # Opens every row with children instead; the response lists them all
    expand_all: bool = False
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)


# Selectable jurisdictions in a subtree (self included) and how many are on.
# Drives the select-all switch.
class SubtreeSelection(SQLModel):
    total: int
    enabled: int
    # User scope: jurisdictions the company hasn't licensed, so the user can never
    # have all of the subtree on
    locked: int


class JurisdictionGridRow(JurisdictionPublic):
    # Indent as shown; less than depth when a filter hides ancestors
    display_depth: int
    # Whether expanding would show anything under the current filter
    has_children: bool
    expanded: bool
    # A match, rather than an ancestor kept for context
    is_match: bool
    # On in the current scope
    enabled: bool
    # The company has opted in
    licensed: bool
    # User scope: the company hasn't opted in, so the row can't be turned on
    locked: bool
    # region-flags keys (e.g. "US-WA"), nearest first: self, then ancestors
    flag_keys: list[str]
    # Rows with children only; counted over the whole, unfiltered subtree
    subtree: SubtreeSelection | None = None
    # Company scope, for company admins: users who opted in
    user_count: int | None = None


class JurisdictionRowsPage(SQLModel):
    data: list[JurisdictionGridRow]
    # Rows in the whole flattened view
    count: int
    skip: int
    # The expansion the page was built with, to hold and edit on the client
    expanded_ids: list[uuid.UUID]


class JurisdictionFacetOption(SQLModel):
    id: uuid.UUID
    label: str
    # Nearest typed ancestor, to tell apart e.g. two cities named "Springfield"
    context: str | None = None
    flag_keys: list[str]


class JurisdictionFacet(SQLModel):
    type: RegionType
    label: str
    options: list[JurisdictionFacetOption]
    # The picks still among the options
    value: list[uuid.UUID]


# What each status tab would show under the current search and facets, counting only
# rows that can be on or off
class JurisdictionStatusCounts(SQLModel):
    all: int
    enabled: int
    available: int
    disabled: int


class JurisdictionSummary(SQLModel):
    # Jurisdictions that can be on or off
    total: int
    # Of those, how many match the filters
    shown: int
    enabled: int
    # User scope: how many the company hasn't licensed
    locked: int | None = None


class JurisdictionFacets(SQLModel):
    # One per region type present, coarsest first; each narrowed by the coarser picks
    facets: list[JurisdictionFacet]
    # The filter's picks with any orphaned by a coarser change dropped
    by_type: dict[RegionType, list[uuid.UUID]]
    status_counts: JurisdictionStatusCounts
    summary: JurisdictionSummary
