import uuid
from typing import Literal

from sqlmodel import Field, SQLModel

from app.jurisdictions.jurisdiction_models import JurisdictionPublic, RegionType
from app.selections.selection_models import SelectionScope

TreeSortBy = Literal["name", "enabled"]
SortDir = Literal["asc", "desc"]
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
