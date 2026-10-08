"""Filtering, faceting and paging for the jurisdiction grid.

Runs over the whole tree in memory: the table is small, and showing a match means
knowing its ancestors. The grid shows matches plus the ancestors kept for context,
flattened in sibling order through the expanded rows.
"""

import uuid
from dataclasses import dataclass

from app.jurisdictions.grid.models import (
    JurisdictionFacet,
    JurisdictionFacetOption,
    JurisdictionFacets,
    JurisdictionFacetsQuery,
    JurisdictionFilters,
    JurisdictionGridRow,
    JurisdictionRowsPage,
    JurisdictionRowsQuery,
    JurisdictionStatusCounts,
    JurisdictionSummary,
    StatusFilter,
    SubtreeSelection,
)
from app.jurisdictions.models import Jurisdiction, RegionType
from app.jurisdictions.tree_index import TreeIndex
from app.selections.models import SelectionScope

TypeFilters = dict[RegionType, list[uuid.UUID]]

TYPE_LABELS = {
    RegionType.country: "Country",
    RegionType.subdivision: "State / Province",
    RegionType.city: "City",
}

# Coarsest first: a finer facet only offers options under the coarser picks
TYPE_ORDER = [RegionType.country, RegionType.subdivision, RegionType.city]


@dataclass(frozen=True)
class Selection:
    """Opt-ins for the scope shown. enabled_ids are on in that scope; licensed_ids are
    the company's, the only ones its users can turn on."""

    scope: SelectionScope
    enabled_ids: frozenset[uuid.UUID]
    licensed_ids: frozenset[uuid.UUID]

    def is_selectable(self, j: Jurisdiction) -> bool:
        return not j.is_structural and (
            self.scope == "company" or j.id in self.licensed_ids
        )


@dataclass
class FilterResult:
    # Matches plus the ancestors kept for context: structural ones, and any that
    # pass the status filter themselves
    visible: set[uuid.UUID]
    # Ancestors of matches, opened so every match is on screen
    expanded: set[uuid.UUID]
    matches: set[uuid.UUID]
    # Matching jurisdictions that can be on or off
    selectable_count: int


def _active_facets(by_type: TypeFilters) -> list[set[uuid.UUID]]:
    return [set(ids) for ids in by_type.values() if ids]


def is_filtering(filters: JurisdictionFilters) -> bool:
    return (
        filters.search.strip() != ""
        or bool(_active_facets(filters.by_type))
        or filters.status != "all"
    )


def matches_status(j: Jurisdiction, status: StatusFilter, sel: Selection) -> bool:
    """Structural rows can't be on or off; they show only as ancestors of matches."""
    if status == "all":
        return True
    if j.is_structural:
        return False
    enabled = j.id in sel.enabled_ids
    if status == "enabled":
        return enabled
    licensed = j.id in sel.licensed_ids
    if status == "available":
        return not enabled and licensed
    return not enabled and not licensed


def _passes_facets(chain: list[Jurisdiction], facets: list[set[uuid.UUID]]) -> bool:
    return all(any(a.id in ids for a in chain) for ids in facets)


def matches_query(
    j: Jurisdiction, chain: list[Jurisdiction], term: str, facets: list[set[uuid.UUID]]
) -> bool:
    """Search and facets, everything but status."""
    if not _passes_facets(chain, facets):
        return False
    return (
        not term
        or term in j.name.lower()
        or (j.code is not None and term in j.code.lower())
    )


def filter_tree(
    index: TreeIndex, filters: JurisdictionFilters, sel: Selection
) -> FilterResult | None:
    if not is_filtering(filters):
        return None
    term = filters.search.strip().lower()
    facets = _active_facets(filters.by_type)
    result = FilterResult(
        visible=set(), expanded=set(), matches=set(), selectable_count=0
    )
    for j in index.nodes:
        if not matches_status(j, filters.status, sel):
            continue
        chain = index.chain(j)
        if not matches_query(j, chain, term, facets):
            continue
        result.matches.add(j.id)
        result.visible.add(j.id)
        if not j.is_structural:
            result.selectable_count += 1
        # Ancestors that fail the status filter stay hidden; the match is shown
        # under the nearest ancestor that is kept
        for a in chain[1:]:
            result.expanded.add(a.id)
            if a.is_structural or matches_status(a, filters.status, sel):
                result.visible.add(a.id)
    return result


def status_counts(
    index: TreeIndex, filters: JurisdictionFilters, sel: Selection
) -> JurisdictionStatusCounts:
    term = filters.search.strip().lower()
    facets = _active_facets(filters.by_type)
    counts = JurisdictionStatusCounts(all=0, enabled=0, available=0, disabled=0)
    for j in index.nodes:
        if j.is_structural or not matches_query(j, index.chain(j), term, facets):
            continue
        counts.all += 1
        if j.id in sel.enabled_ids:
            counts.enabled += 1
        elif j.id in sel.licensed_ids:
            counts.available += 1
        else:
            counts.disabled += 1
    return counts


def _own_flag_key(index: TreeIndex, j: Jurisdiction) -> str | None:
    if not j.code:
        return None
    if j.region_type == RegionType.country:
        return j.code
    if j.region_type == RegionType.subdivision:
        country = next(
            (a for a in index.chain(j)[1:] if a.region_type == RegionType.country),
            None,
        )
        if country and country.code:
            return f"{country.code}-{j.code}"
    return None


def flag_keys(index: TreeIndex, j: Jurisdiction) -> list[str]:
    """region-flags keys, nearest first. Structural groupings get no flag; rows without
    one of their own (e.g. a city) fall back to their nearest ancestor's."""
    if j.is_structural and not j.region_type:
        return []
    keys = (_own_flag_key(index, a) for a in index.chain(j))
    return [k for k in keys if k]


def facets_for(index: TreeIndex, by_type: TypeFilters) -> list[JurisdictionFacet]:
    """One facet per region type present, each narrowed by the coarser picks."""
    present = {j.region_type for j in index.nodes}
    facets: list[JurisdictionFacet] = []
    coarser: list[set[uuid.UUID]] = []
    for type_ in TYPE_ORDER:
        if type_ not in present:
            continue
        options = []
        for j in index.nodes:
            if j.region_type != type_:
                continue
            chain = index.chain(j)
            if not _passes_facets(chain, coarser):
                continue
            options.append(
                JurisdictionFacetOption(
                    id=j.id,
                    label=j.name,
                    context=next((a.name for a in chain[1:] if a.region_type), None),
                    flag_keys=flag_keys(index, j),
                )
            )
        options.sort(key=lambda o: o.label.casefold())
        # Picks orphaned by a coarser change drop out
        allowed = {o.id for o in options}
        value = [i for i in by_type.get(type_, []) if i in allowed]
        facets.append(
            JurisdictionFacet(
                type=type_, label=TYPE_LABELS[type_], options=options, value=value
            )
        )
        if value:
            coarser.append(set(value))
    return facets


def _pruned(
    index: TreeIndex, filters: JurisdictionFilters
) -> tuple[JurisdictionFilters, list[JurisdictionFacet]]:
    facets = facets_for(index, filters.by_type)
    by_type = {f.type: f.value for f in facets if f.value}
    return filters.model_copy(update={"by_type": by_type}), facets


def subtree_selections(
    index: TreeIndex, sel: Selection
) -> dict[uuid.UUID, SubtreeSelection]:
    """Select-all state per parent, counted over the whole tree so filters and
    collapsed rows don't change what "all" means."""
    out: dict[uuid.UUID, SubtreeSelection] = {}

    def count(j: Jurisdiction) -> SubtreeSelection:
        selectable = sel.is_selectable(j)
        s = SubtreeSelection(
            total=int(selectable),
            enabled=int(selectable and j.id in sel.enabled_ids),
            locked=int(not selectable and not j.is_structural),
        )
        children = index.children(j)
        for c in children:
            cs = count(c)
            s.total += cs.total
            s.enabled += cs.enabled
            s.locked += cs.locked
        if children:
            out[j.id] = s
        return s

    for root in index.children_of.get(None, []):
        count(root)
    return out


def default_expanded(index: TreeIndex, filtered: FilterResult | None) -> set[uuid.UUID]:
    if filtered:
        return set(filtered.expanded)
    return {j.id for j in index.children_of.get(None, [])}


def flatten(
    index: TreeIndex,
    filtered: FilterResult | None,
    expanded: set[uuid.UUID],
    start: int,
    limit: int,
) -> tuple[list[tuple[Jurisdiction, int]], int]:
    """The rows in [start, start + limit) with their display depth, and the total.
    Hidden rows are walked through, so their visible descendants move up a level."""
    page: list[tuple[Jurisdiction, int]] = []
    total = 0
    end = start + limit

    def walk(parent_id: uuid.UUID | None, depth: int) -> None:
        nonlocal total
        for j in index.children_of.get(parent_id, []):
            if filtered and j.id not in filtered.visible:
                if j.id in filtered.expanded:
                    walk(j.id, depth)
                continue
            if start <= total < end:
                page.append((j, depth))
            total += 1
            if j.id in expanded:
                walk(j.id, depth + 1)

    walk(None, 0)
    return page, total


def summary(
    index: TreeIndex, sel: Selection, filtered: FilterResult | None
) -> JurisdictionSummary:
    selectable = [j for j in index.nodes if not j.is_structural]
    return JurisdictionSummary(
        total=len(selectable),
        shown=filtered.selectable_count if filtered else len(selectable),
        enabled=len(sel.enabled_ids),
        locked=(
            sum(1 for j in selectable if j.id not in sel.licensed_ids)
            if sel.scope == "user"
            else None
        ),
    )


def build_rows_page(
    index: TreeIndex,
    sel: Selection,
    query: JurisdictionRowsQuery,
    user_counts: dict[uuid.UUID, int] | None = None,
) -> JurisdictionRowsPage:
    filters, _ = _pruned(index, query.filters)
    filtered = filter_tree(index, filters, sel)
    if query.expand_all:
        expanded = {j.id for j in index.nodes if index.children(j)}
    elif query.expanded_ids is not None:
        expanded = set(query.expanded_ids)
    else:
        expanded = default_expanded(index, filtered)
    page, total = flatten(index, filtered, expanded, query.skip, query.limit)
    subtrees = subtree_selections(index, sel)

    # Rows with something to show under them. Every ancestor of a match is walked,
    # so a visible descendant anywhere below means expanding shows it.
    with_shown_children: set[uuid.UUID] | None = None
    if filtered:
        with_shown_children = {
            a.id for vid in filtered.visible for a in index.chain(index.by_id[vid])[1:]
        }

    rows = []
    for j, depth in page:
        licensed = j.id in sel.licensed_ids
        children = index.children(j)
        rows.append(
            JurisdictionGridRow.model_validate(
                j,
                update={
                    "child_count": len(children),
                    "display_depth": depth,
                    "has_children": (
                        j.id in with_shown_children
                        if with_shown_children is not None
                        else bool(children)
                    ),
                    "expanded": j.id in expanded,
                    "is_match": filtered is None or j.id in filtered.matches,
                    "enabled": j.id in sel.enabled_ids,
                    "licensed": licensed,
                    "locked": sel.scope == "user"
                    and not licensed
                    and not j.is_structural,
                    "flag_keys": flag_keys(index, j),
                    "subtree": subtrees.get(j.id),
                    "user_count": (
                        user_counts.get(j.id, 0) if user_counts is not None else None
                    ),
                },
            )
        )
    return JurisdictionRowsPage(
        data=rows,
        count=total,
        skip=query.skip,
        expanded_ids=[j.id for j in index.nodes if j.id in expanded],
    )


def build_facets(
    index: TreeIndex, sel: Selection, query: JurisdictionFacetsQuery
) -> JurisdictionFacets:
    filters, facets = _pruned(index, query.filters)
    return JurisdictionFacets(
        facets=facets,
        by_type=filters.by_type,
        status_counts=status_counts(index, filters, sel),
        summary=summary(index, sel, filter_tree(index, filters, sel)),
    )
