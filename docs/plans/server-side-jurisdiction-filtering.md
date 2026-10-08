# Plan: server-side jurisdiction filtering and paging

## Status

- Backend: done (2026-10-07). Endpoints, `app/jurisdiction_query.py`, tests, client
  regenerated.
- UI: done (2026-10-07); see "UI design" below. Verified in the browser: paging
  (20-row blocks), expand / collapse / expand all, search, status tabs, toggles,
  confirm dialog, company scope and sort.

## Goal

Move all filter logic out of `frontend/src/components/Jurisdictions/filterTree.ts`
(`filterTree`, `statusCounts`, `facetsFor`, `withFacet`) and the whole-tree parts of
`JurisdictionGridService.buildRows` (flatten, display depth, select-all subtree counts,
summary) to the backend. The client sends one POST with filters, sort, expansion and a
`start` / `limit` window and gets back exactly the rows to render.

## Paging model

AG Grid Community has no server-side tree row model, so the server pages the
**flattened visible tree**, the same list `buildRows` produces today.

- The client sends `expanded_ids`; the server walks the filtered tree and returns
  `rows[start:start+limit]` plus `total` (flattened row count).
- `expanded_ids: null` means the server default: the roots when browsing, the
  ancestors of every match when filtering (what `useExpandedState` does today). The
  response echoes the expanded set it used so the client can hold it and edit it.
- Hidden ancestors are walked through, so their visible descendants move up a level
  (`display_depth`).

## Endpoints

All read-only endpoints are POSTs so large filter / expansion payloads fit.

### `POST /jurisdictions/rows` — a page of grid rows

Body `JurisdictionRowsQuery`:

| field          | type                                   | notes                              |
| -------------- | -------------------------------------- | ---------------------------------- |
| `scope`        | `"company" \| "user"`                  | whose opt-ins count as enabled     |
| `filters`      | `JurisdictionFilters`                  | `search`, `by_type`, `status`      |
| `sort_by`      | `"name" \| "enabled" \| null`          | sibling order, as `GET /tree`      |
| `sort_dir`     | `"asc" \| "desc"`                      |                                    |
| `expanded_ids` | `uuid[] \| null`                       | null = server default              |
| `start`        | `int >= 0`                             |                                    |
| `limit`        | `1..500`, default 100                  |                                    |

Response `JurisdictionRowsPage`: `data: JurisdictionGridRow[]`, `total`, `start`,
`expanded_ids`.

`JurisdictionGridRow` extends `JurisdictionPublic` with:

- `display_depth` — indent as shown; less than `depth` when a filter hides ancestors
- `has_children` — expanding would show something under the current filter
- `expanded`, `is_match` (a match, not an ancestor kept for context; drives highlight)
- `enabled` (on in this scope), `licensed` (company opted in), `locked` (user scope,
  not structural and not licensed)
- `flag_keys` — region-flags keys, nearest first (self, then ancestors); the client
  shows the first one it has an SVG for. Replaces the client's ancestor walk in
  `flags.ts`, since it no longer has the whole tree.
- `subtree: {total, enabled, locked} | null` — select-all state over the whole,
  unfiltered subtree (rows with children only)
- `user_count` — company scope, company admins / superusers only

### `POST /jurisdictions/facets` — everything that changes with filters, not scroll

Body `JurisdictionFacetsQuery`: `scope`, `filters`.

Response `JurisdictionFacets`:

- `facets` — one per region type present, coarsest first; finer facets only offer
  options under the coarser picks. Options carry `id`, `label`, `context` (nearest
  typed ancestor's name), `flag_keys`.
- `by_type` — the picks with orphans dropped (replaces `withFacet`)
- `status_counts` — `{all, enabled, available, disabled}` under search + facets
- `summary` — `{total, shown, enabled, locked}`

### Subtree toggles (client no longer has the tree)

- `POST /companies/{company_id}/jurisdictions/subtree` (company admin)
- `POST /users/me/jurisdictions/subtree`

Body `{root_id, enabled}`; turns every selectable jurisdiction in the subtree on or off
(user scope: only licensed ones). Returns `JurisdictionIds`.

`POST /companies/{company_id}/jurisdictions/affected-users` also accepts `root_ids`,
expanded to their selectable subtrees, so the confirm-disable dialog needn't send ids.

`GET /jurisdictions/tree` stays until the UI has moved over, then goes with
`filterTree.ts`.

## Semantics (ported 1:1 from `filterTree.ts`)

- Status: `all` passes everything; structural rows never pass another status.
  `enabled` = in the scope's opt-ins; `available` = off but licensed;
  `disabled` = off and not licensed.
- Facets: AND across region types, OR within one; a row passes a type when it or an
  ancestor is picked.
- Search: case-insensitive substring of name or code.
- Visible = matches, plus each match's ancestors that are structural or pass the
  status filter. Every ancestor of a match is in the filter's expanded set.
- `shown` counts non-structural matches.

## Implementation

1. `app/models.py` — request / response schemas; `TreeSortBy`, `SortDir`,
   `SelectionScope`, `StatusFilter` literals move here (crud re-exports them).
2. `app/jurisdiction_query.py` — pure functions over an in-memory `TreeIndex`
   (`by_id`, `children_of`, cached ancestor chains) and a `Selection`
   (scope, enabled ids, licensed ids). Loading the whole table is one cheap SELECT;
   if it grows, facets can move to SQL via the materialized `path` column.
3. `app/crud.py` — `get_jurisdiction_selection`, `get_selectable_subtree_ids`,
   `toggle_company_subtree`, `toggle_user_subtree`.
4. Routes — `POST /rows` and `/facets` registered before `/{jurisdiction_id}`;
   subtree routes in `companies.py` / `users.py`.
5. Tests — `tests/test_jurisdiction_query.py` (pure functions) and API tests in
   `tests/api/routes/test_jurisdictions.py`.
6. Regenerate the OpenAPI client for the UI turn.

## UI design

- **Rows: AG Grid infinite row model.** `JurisdictionRowSource` implements the
  grid's `IDatasource`: each block becomes a `POST /jurisdictions/rows` with the
  block's `start` / `limit`, the grid's sort model, the (deferred) filters and the
  current expansion; `total` becomes the grid's last row. Blocks load as you scroll.
  - Filter change: scroll to top + `purgeInfiniteCache()`.
  - Expand / collapse / expand all / collapse all and saves:
    `refreshInfiniteCache()`, which reloads the loaded blocks in place and keeps the
    scroll position.
  - Expansion lives in the row source, separately for browsing and filtering (as
    `useExpandedState` did). `null` asks for the server default; the echoed
    `expanded_ids` is adopted only if the expansion hasn't changed since the
    request. Expand all sends `expand_all` (added to the backend for this).
- **Toolbar / counts / summary:** `useSuspenseQuery` on `POST /jurisdictions/facets`
  keyed on scope + `useDeferredValue(filters)`, so old counts stay up while new ones
  load. The server's pruned `by_type` is synced back into the filter state.
- **Saves:** every switch (single row or select-all) goes through the subtree
  endpoints; a single row is a subtree of one. The confirm-disable dialog asks
  affected-users by `root_ids`. Single toggles update the row in place
  optimistically, then the cache refreshes (ancestors' select-all counts change).
- **Row mapping:** `JurisdictionGridService.toRow` turns a server row into the
  grid's `JurisdictionRow` (disabled reason, unlock link, flag URL from
  `flag_keys`). Re-applied to loaded rows when its inputs (e.g. admins) change.
- **Selection sheet:** still needs the whole tree for its rolled-up summary; it now
  loads `GET /tree` only when opened. Not filter logic.
- **Removed:** `filterTree.ts`, `buildRows`, `childrenOf`, `subtreeOf`, client sort
  no-ops, `userCountsQuery` (user counts come on the rows).
