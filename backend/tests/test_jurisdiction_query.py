import uuid
from typing import Any

import pytest

from app import jurisdiction_query as jq
from app.models import (
    Jurisdiction,
    JurisdictionFacetsQuery,
    JurisdictionFilters,
    JurisdictionRowsQuery,
    RegionType,
    SelectionScope,
)


class World:
    """
    United States (country US)
      States (structural)
        Washington (subdivision WA)
          Seattle (city SEA)
          Springfield (city SPW)
        Illinois (subdivision IL)
          Springfield (city SPI)
      National
    Canada (country CA)
      British Columbia (subdivision BC)
        Vancouver (city VAN)
    """

    def __init__(self) -> None:
        self.nodes: list[Jurisdiction] = []
        self.us = self.add("United States", None, "US", RegionType.country)
        self.states = self.add("States", self.us, is_structural=True)
        self.wa = self.add("Washington", self.states, "WA", RegionType.subdivision)
        self.seattle = self.add("Seattle", self.wa, "SEA", RegionType.city)
        self.spw = self.add("Springfield", self.wa, "SPW", RegionType.city)
        self.il = self.add("Illinois", self.states, "IL", RegionType.subdivision)
        self.spi = self.add("Springfield", self.il, "SPI", RegionType.city)
        self.national = self.add("National", self.us)
        self.ca = self.add("Canada", None, "CA", RegionType.country)
        self.bc = self.add("British Columbia", self.ca, "BC", RegionType.subdivision)
        self.van = self.add("Vancouver", self.bc, "VAN", RegionType.city)
        self.index = jq.TreeIndex(self.nodes)

    def add(
        self,
        name: str,
        parent: Jurisdiction | None,
        code: str | None = None,
        region_type: RegionType | None = None,
        is_structural: bool = False,
    ) -> Jurisdiction:
        id_ = uuid.uuid4()
        j = Jurisdiction(
            id=id_,
            name=name,
            parent_id=parent.id if parent else None,
            code=code,
            region_type=region_type,
            is_structural=is_structural,
            depth=parent.depth + 1 if parent else 0,
            sort_order=len(self.nodes),
            path=f"{parent.path if parent else '/'}{id_.hex}/",
            name_path=name,
        )
        self.nodes.append(j)
        return j


def sel(
    scope: SelectionScope = "company",
    enabled: list[Jurisdiction] | None = None,
    licensed: list[Jurisdiction] | None = None,
) -> jq.Selection:
    licensed_ids = frozenset(j.id for j in licensed or [])
    enabled_ids = (
        licensed_ids if scope == "company" else frozenset(j.id for j in enabled or [])
    )
    return jq.Selection(scope=scope, enabled_ids=enabled_ids, licensed_ids=licensed_ids)


def filters(**kwargs: Any) -> JurisdictionFilters:
    return JurisdictionFilters(**kwargs)


def names(index: jq.TreeIndex, ids: set[uuid.UUID]) -> set[str]:
    return {index.by_id[i].name for i in ids}


@pytest.fixture
def w() -> World:
    return World()


def test_no_filter(w: World) -> None:
    assert jq.filter_tree(w.index, filters(), sel()) is None
    assert jq.filter_tree(w.index, filters(search="  "), sel()) is None


def test_search_keeps_ancestors_and_opens_them(w: World) -> None:
    r = jq.filter_tree(w.index, filters(search="SPRING"), sel())
    assert r
    assert r.matches == {w.spw.id, w.spi.id}
    assert r.visible == {w.spw.id, w.spi.id, w.wa.id, w.il.id, w.states.id, w.us.id}
    assert r.expanded == {w.wa.id, w.il.id, w.states.id, w.us.id}
    assert r.selectable_count == 2


def test_search_matches_code(w: World) -> None:
    r = jq.filter_tree(w.index, filters(search="sea"), sel())
    assert r and r.matches == {w.seattle.id}


def test_facets_and_across_types_or_within(w: World) -> None:
    # Picking a country keeps its whole subtree
    r = jq.filter_tree(w.index, filters(by_type={RegionType.country: [w.ca.id]}), sel())
    assert r and r.matches == {w.ca.id, w.bc.id, w.van.id}

    r = jq.filter_tree(
        w.index,
        filters(by_type={RegionType.subdivision: [w.wa.id, w.il.id]}),
        sel(),
    )
    assert r and r.matches == {w.wa.id, w.seattle.id, w.spw.id, w.il.id, w.spi.id}

    r = jq.filter_tree(
        w.index,
        filters(
            search="spring",
            by_type={
                RegionType.country: [w.us.id],
                RegionType.subdivision: [w.il.id],
            },
        ),
        sel(),
    )
    assert r and r.matches == {w.spi.id}


def test_status_hides_ancestors_that_fail_it(w: World) -> None:
    s = sel("user", enabled=[w.seattle], licensed=[w.seattle, w.wa])
    r = jq.filter_tree(w.index, filters(status="enabled"), s)
    assert r and r.matches == {w.seattle.id}
    # Structural ancestors stay for context; Washington and the US are off
    assert r.visible == {w.seattle.id, w.states.id}

    page, total = jq.flatten(w.index, r, r.expanded, 0, 100)
    assert [(j.name, d) for j, d in page] == [("States", 0), ("Seattle", 1)]
    assert total == 2

    r = jq.filter_tree(w.index, filters(status="available"), s)
    assert r and r.matches == {w.wa.id}
    r = jq.filter_tree(w.index, filters(status="disabled"), s)
    assert r and names(w.index, r.matches) == {
        "United States",
        "Springfield",
        "Illinois",
        "National",
        "Canada",
        "British Columbia",
        "Vancouver",
    }
    # Structural rows never match a status
    assert w.states.id not in r.matches


def test_status_counts(w: World) -> None:
    s = sel("user", enabled=[w.seattle], licensed=[w.seattle, w.wa])
    counts = jq.status_counts(w.index, filters(search="s"), s)
    # Non-structural rows with an "s": United States, Washington, Seattle, Springfield
    # x2, Illinois, British Columbia
    assert counts.model_dump() == {
        "all": 7,
        "enabled": 1,
        "available": 1,
        "disabled": 5,
    }


def test_facets_cascade_and_prune(w: World) -> None:
    facets = jq.facets_for(
        w.index,
        {RegionType.country: [w.ca.id], RegionType.subdivision: [w.wa.id]},
    )
    by_type = {f.type: f for f in facets}
    assert [f.type for f in facets] == jq.TYPE_ORDER
    assert [o.label for o in by_type[RegionType.country].options] == [
        "Canada",
        "United States",
    ]
    assert by_type[RegionType.country].value == [w.ca.id]
    # Washington isn't under Canada, so the pick drops out
    assert [o.label for o in by_type[RegionType.subdivision].options] == [
        "British Columbia"
    ]
    assert by_type[RegionType.subdivision].value == []
    assert [o.label for o in by_type[RegionType.city].options] == ["Vancouver"]

    cities = jq.facets_for(w.index, {})[2].options
    assert sorted(o.context or "" for o in cities if o.label == "Springfield") == [
        "Illinois",
        "Washington",
    ]


def test_flag_keys(w: World) -> None:
    assert jq.flag_keys(w.index, w.us) == ["US"]
    assert jq.flag_keys(w.index, w.wa) == ["US-WA", "US"]
    assert jq.flag_keys(w.index, w.seattle) == ["US-WA", "US"]
    assert jq.flag_keys(w.index, w.national) == ["US"]
    assert jq.flag_keys(w.index, w.states) == []


def test_subtree_selections(w: World) -> None:
    s = sel("user", enabled=[w.seattle], licensed=[w.seattle, w.wa])
    subtrees = jq.subtree_selections(w.index, s)
    assert subtrees[w.wa.id].model_dump() == {"total": 2, "enabled": 1, "locked": 1}
    assert subtrees[w.us.id].model_dump() == {"total": 2, "enabled": 1, "locked": 5}
    assert w.seattle.id not in subtrees

    company = jq.subtree_selections(w.index, sel(licensed=[w.seattle]))
    assert company[w.us.id].model_dump() == {"total": 7, "enabled": 1, "locked": 0}


def test_flatten_pages(w: World) -> None:
    expanded = {j.id for j in w.nodes}
    everything, total = jq.flatten(w.index, None, expanded, 0, 100)
    assert total == len(w.nodes)
    assert [j.id for j, _ in everything] == [j.id for j in w.nodes]

    page, total = jq.flatten(w.index, None, expanded, 3, 4)
    assert total == len(w.nodes)
    assert page == everything[3:7]

    page, total = jq.flatten(w.index, None, jq.default_expanded(w.index, None), 0, 100)
    assert [j.name for j, _ in page] == [
        "United States",
        "States",
        "National",
        "Canada",
        "British Columbia",
    ]


def test_build_rows_page(w: World) -> None:
    s = sel("user", enabled=[w.seattle], licensed=[w.seattle, w.wa])
    page = jq.build_rows_page(
        w.index, s, JurisdictionRowsQuery(filters=filters(search="seattle"))
    )
    rows = {r.name: r for r in page.data}
    assert list(rows) == ["United States", "States", "Washington", "Seattle"]
    assert page.total == 4
    assert set(page.expanded_ids) == {w.us.id, w.states.id, w.wa.id}
    assert rows["Washington"].has_children and rows["Washington"].expanded
    assert not rows["Washington"].is_match and rows["Seattle"].is_match
    assert rows["Seattle"].enabled and rows["Seattle"].licensed
    assert rows["United States"].locked and not rows["States"].locked
    assert rows["Washington"].subtree and rows["Washington"].subtree.total == 2
    assert rows["Seattle"].display_depth == 3
    assert rows["Seattle"].user_count is None

    # A match whose children don't match has nothing to show when expanded
    page = jq.build_rows_page(
        w.index,
        s,
        JurisdictionRowsQuery(filters=filters(search="washington")),
    )
    wa = next(r for r in page.data if r.name == "Washington")
    assert wa.child_count == 2 and not wa.has_children

    # Collapsing a row the filter opened hides what's under it
    page = jq.build_rows_page(
        w.index,
        s,
        JurisdictionRowsQuery(
            filters=filters(search="seattle"), expanded_ids=[w.us.id]
        ),
    )
    assert [r.name for r in page.data] == ["United States", "States"]


def test_build_rows_drops_orphaned_picks(w: World) -> None:
    query = JurisdictionRowsQuery(
        filters=filters(
            by_type={RegionType.country: [w.ca.id], RegionType.city: [w.seattle.id]}
        )
    )
    page = jq.build_rows_page(w.index, sel(), query)
    assert [r.name for r in page.data] == ["Canada", "British Columbia", "Vancouver"]


def test_build_facets(w: World) -> None:
    s = sel("user", enabled=[w.seattle], licensed=[w.seattle, w.wa])
    result = jq.build_facets(
        w.index,
        s,
        JurisdictionFacetsQuery(
            scope="user",
            filters=filters(
                status="enabled",
                by_type={
                    RegionType.country: [w.us.id],
                    RegionType.city: [w.van.id],
                },
            ),
        ),
    )
    assert result.by_type == {RegionType.country: [w.us.id]}
    # Everything non-structural under the US, whatever the status
    assert result.status_counts.all == 7
    assert result.summary.model_dump() == {
        "total": 10,
        "shown": 1,
        "enabled": 1,
        "locked": 8,
    }


def test_build_rows_expand_all(w: World) -> None:
    page = jq.build_rows_page(w.index, sel(), JurisdictionRowsQuery(expand_all=True))
    assert page.total == len(w.nodes)
    assert set(page.expanded_ids) == {
        w.us.id,
        w.states.id,
        w.wa.id,
        w.il.id,
        w.ca.id,
        w.bc.id,
    }
