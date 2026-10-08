# Plan: API architecture fixes

## Status

- In progress. Phases 1 (error model, list envelope) and 2 (lifecycle invariants) are done
  and were removed from this file. Next up is Phase 3. Findings come from the adversarial
  API review (2026-10-07).
- In scope: review items 2, 3, 7, 9, 10, 11 and all the Low items.
- Already in place for the later phases:
  - `app/errors.py`: `ApiError` and its subclasses, including `PreconditionFailed` (412) and
    `PreconditionRequired` (428), plus the `errors(...)` OpenAPI helper. Every route documents
    its non-2xx responses as `ErrorResponse`, so new routes add `errors(412, 428)` where they apply.
  - Error body: `{detail, code, context}`. Ids go in `context`, never in `detail`.
  - Lists: `{data, count}`, with `skip` / `limit` bounded `ge=1, le=500`.
  - Tests: `tests/utils/utils.py::assert_error(r, status, code)` checks the status and `code`.
  - `crud.delete_user` and `update_user` enforce the last-company-admin and last-superuser
    rules. A company move resets the role to member.
- Out of scope (not chosen): #1 signup default role, #4 token lifetime / revocation on
  credential change, #5 recovery enumeration, #6 `FASTAPI_ENV` coupling, #8 implicit
  tenant addressing. New users still default to company `admin`.

## Goal

Make the selection API safe to write concurrently, consistent in shape, and stable
against storage changes. Then move the grid view-model out of the resource namespace.
This is a breaking change for `/api/v1`. The only clients are this frontend, the
Playwright helpers and the `/service` consumer, so it ships in place with a regenerated
client rather than as a `/v2`. The `/service` contract does not change.

## Ground rules for executing

- Work in phases, in order. Each phase ends green: `uv run pytest` in `backend/`,
  `bash scripts/generate-client.sh` from the repo root, `bunx tsc --noEmit` in
  `frontend/`, then `bunx playwright test` with the backend and Vite running.
- Use bun / bunx for all frontend and script work (see `CLAUDE.md`), and 4-space indent.
- Alembic head is `9d3b6e1f4a27` (`drop_item`, currently untracked). New migrations
  chain from it.
- Never hand-edit `frontend/src/client/**`. Regenerate it.

---

## Phase 3: one selection resource with versioned writes (#7, #2)

### 3.1 Target shape

There are three owners, all with the same sub-resource:

- `{owner}` = `users/me` | `users/{user_id}` | `companies/{company_id}`
- Auth: `users/me` is the user. `users/{id}` is a company admin of that user or a
  superuser. Companies: reads need a member, writes need an admin.

| Method + path | Body | Response | Notes |
|---|---|---|---|
| `GET {owner}/jurisdictions` | none | `JurisdictionSelectionOut` + `ETag` | ids only |
| `PUT {owner}/jurisdictions` | `JurisdictionSelection` | `JurisdictionSelectionOut` + `ETag` | **`If-Match` required** (428 without it, 412 on mismatch). Empty list → 422 `use_delete_to_clear`. |
| `PATCH {owner}/jurisdictions` | `SelectionChange` | `JurisdictionSelectionOut` + `ETag` | `If-Match` optional, checked when sent |
| `DELETE {owner}/jurisdictions` | none | `JurisdictionSelectionOut` + `ETag` | **`If-Match` required**. The only way to clear. |
| `POST companies/{id}/jurisdictions/preview` | `SelectionChange` | `SelectionPreview` + `ETag` | Dry run. Nothing is written. |

New models (`models.py`):

```python
class JurisdictionSelectionOut(SQLModel):
    jurisdiction_ids: list[uuid.UUID]
    count: int
    version: int

# Applied in order: add, add_subtrees, remove, remove_subtrees. Ids in both add and remove → 422
class SelectionChange(SQLModel):
    add: list[uuid.UUID] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)
    add_subtrees: list[uuid.UUID] = Field(default_factory=list)
    remove_subtrees: list[uuid.UUID] = Field(default_factory=list)

class SelectionPreview(SQLModel):
    version: int                     # pass back as If-Match to commit exactly this preview
    added: list[uuid.UUID]
    removed: list[uuid.UUID]
    affected_users: JurisdictionAffectedUsers
```

### 3.2 Endpoints that are removed

- `GET {owner}/jurisdictions/ids`: replaced by `GET {owner}/jurisdictions`.
- The old `GET {owner}/jurisdictions` full-object variant: the frontend only takes ids
  from it (`idsOf` in `JurisdictionGridService.ts`). Clients that need names use
  `/jurisdictions/tree`.
- `POST {owner}/jurisdictions/subtree`: replaced by `PATCH` with `add_subtrees` /
  `remove_subtrees`. This also covers Low "toggle is really set". The missing
  `users/{id}` subtree variant comes for free.
- `GET companies/{id}/jurisdictions/user-counts`: duplicated by `user_count` on grid rows.
- `POST companies/{id}/jurisdictions/affected-users`: replaced by `preview`.
- **Kept unchanged:** `GET /service/users/{id}/jurisdiction-ids`. External consumers and
  the README depend on it. Switch it onto the shared crud read.

### 3.3 Versioning (migration + crud)

- Migration `xxxx_add_selection_versions` (down_revision `9d3b6e1f4a27`) adds
  `company.jurisdictions_version INTEGER NOT NULL DEFAULT 0` and
  `user.jurisdictions_version INTEGER NOT NULL DEFAULT 0`. Add both fields to the models.
  They are not exposed on `CompanyPublic` / `UserPublic`.
- ETag format: `W/"c-<company_id>-<version>"` / `W/"u-<user_id>-<version>"`.
  - Parse `If-Match` in one dependency, `if_match_version(request) -> int | None`. It
    accepts the ETag or a bare integer, and anything else → 412.
- Compare-and-swap inside the write transaction. A read-then-check is not enough:

```python
result = session.exec(
    update(Company)
    .where(col(Company.id) == company_id, col(Company.jurisdictions_version) == expected)
    .values(jurisdictions_version=Company.jurisdictions_version + 1)
)
if result.rowcount != 1:
    raise PreconditionFailed("The license changed since you loaded it", context={"version": current})
```

  - When `If-Match` is absent (PATCH only), bump unconditionally.
- **Cascade bumps users.** `set_company_jurisdictions` deletes `CompanyJurisdiction`
  rows, and the FK cascade removes user opt-ins without touching those users' versions.
  Before the delete, run `UPDATE user SET jurisdictions_version = jurisdictions_version + 1
  WHERE id IN (SELECT user_id FROM userjurisdiction WHERE company_id = :c AND
  jurisdiction_id IN :removed)`.
- `update_user` company move (which clears opt-ins) also bumps that user's version.

### 3.4 Crud refactor (`crud.py`)

- Replace `set_company_jurisdictions`, `set_user_jurisdictions`,
  `toggle_company_subtree` and `toggle_user_subtree` with one core:

```python
def apply_selection(*, session, owner: SelectionOwner, wanted: set[uuid.UUID], expected_version: int | None) -> Selection...
def resolve_change(*, session, owner, change: SelectionChange) -> set[uuid.UUID]   # current ∪ adds − removes
def preview_company_change(*, session, company_id, change) -> SelectionPreview
```

- `SelectionOwner` is a small dataclass `(kind: Literal["company", "user"], id, company_id)`.
- User-scope `add_subtrees` keeps today's behavior: it intersects with the company's
  licensed ids, so locked rows are skipped. Explicit `add` of an unlicensed id is still
  rejected (422 `jurisdiction_not_licensed`).
- `get_subtree_ids` already raises `InvalidInput(code="unknown_jurisdiction")`, so there's
  nothing to change there.

### 3.5 Routes

- New `backend/app/api/routes/selections.py` holds the five handlers once. Mount them on
  the three owner prefixes through a small factory, or three thin routers calling shared
  functions. Pick whichever keeps operationIds readable, e.g.
  `users-read_my_jurisdictions`, `users-patch_user_jurisdictions`,
  `companies-preview_company_jurisdictions`.
- Delete the selection handlers from `users.py` and `companies.py`.
- Set the `ETag` response header on every selection response. Add `expose_headers=["ETag"]`
  to the CORS middleware in `main.py` so the browser can read it.

### 3.6 Frontend

- `JurisdictionGridService.ts`:
  - `companyIdsQuery` / `myIdsQuery` call the new GET and keep `version` in the query
    data.
  - `saveSubtree` becomes `PATCH` with `{add_subtrees: [rootId]}` or
    `{remove_subtrees: [rootId]}`.
  - `affectedUsers` becomes `preview` with `{remove_subtrees: [rootId]}` and returns
    `{version, affected_users}`.
- `useSelectionMutation.ts` / `JurisdictionGrid.tsx`: the confirm-disable flow passes the
  preview's `version` as `If-Match` on the PATCH it commits.
  - On 412, show the toast "The license changed while you were reviewing. Showing the
    latest." Then invalidate the queries and reopen the preview.
  - Plain toggles (no confirm) send no `If-Match`.
- `SelectionSheet.tsx`: change the endpoint label to `GET /api/v1/users/me/jurisdictions`
  (and the company variant).
- `frontend/tests/utils/jurisdictions.ts`:
  - `setCompanyJurisdictions` / `setMyJurisdictions` either GET first and send
    `If-Match`, or use `PATCH {add}`. Use PATCH, since it's simpler for fixtures.
  - The `read*JurisdictionIds` helpers call the new GET.
- `frontend/tests/jurisdictions.spec.ts:153`: update the endpoint text.

### 3.7 Tests (rewrite the selection parts of `test_users.py`, `test_companies.py`; add `test_selections.py`)

- PUT without `If-Match` → 428. PUT with a stale version → 412, and nothing changes. The
  current version → 200 and version+1.
- Two sequential PUTs from the same snapshot: the first wins and the second gets 412.
  This is the lost-update case from the review.
- PUT `[]` → 422. DELETE with `If-Match` clears.
- Dropping a jurisdiction from the company bumps every affected user's version, and does
  not bump unaffected users.
- PATCH merge semantics, the add/remove conflict → 422, and user `add_subtrees` skips
  locked rows.
- Preview writes nothing. Its version, used as `If-Match`, commits. A license change
  between preview and commit → 412.
- `users/{id}` PATCH is allowed for a company admin and a superuser, and gets 403 for a
  member and for an admin of another company.
- `/service` response is unchanged.

---

## Phase 4: contract cleanup and the view namespace (#10, #11)

### 4.1 Stop exposing storage internals (#10)

- `JurisdictionPublic` drops `path`, `depth` and `sort_order`. It keeps `id`,
  `parent_id`, `name`, `name_path`, `code`, `region_type`, `is_structural` and
  `child_count`.
- The frontend doesn't read them. The only `depth` it uses comes from `display_depth`.
  Confirm with `bunx tsc --noEmit` after regen.
- Contract: "lists of jurisdictions return siblings in display order". Write that in the
  `/jurisdictions` and `/jurisdictions/tree` docstrings so the client never needs
  `sort_order`.
- `JurisdictionCreate` / `JurisdictionUpdate` keep `sort_order` as an input (a position
  among siblings).
- `JurisdictionGridRow` inherits the trimmed model. Check that
  `jurisdiction_query.build_rows_page` doesn't put the dropped keys into its `update={}`.
- Tests that assert `path` / `depth` in responses: read them from the DB with
  `session.get(Jurisdiction, id)` instead, so the tree invariants stay covered.

### 4.2 Move the grid view-model under `/views` (#11)

- New `backend/app/api/routes/views.py`, `APIRouter(prefix="/views/jurisdiction-grid",
  tags=["views"])`:
  - `POST /views/jurisdiction-grid/rows` (was `/jurisdictions/rows`)
  - `POST /views/jurisdiction-grid/facets` (was `/jurisdictions/facets`)
- Move the two handlers out of `jurisdictions.py`. Add a module docstring saying these
  are UI view models that can change with the grid, and that integrations must use the
  resource endpoints.
- `GET /jurisdictions/tree` drops `sort_by`, `sort_dir` and `scope`, and returns only the
  canonical order. The frontend calls it with no params. Check the call in
  `tests/utils/jurisdictions.ts:51`. `crud.get_jurisdiction_tree` keeps its params for
  the views.
- Frontend: `JurisdictionsService.readJurisdictionRows` / `readJurisdictionFacets` become
  `ViewsService.*` in `JurisdictionGridService.ts` (and `JurisdictionRowSource.ts`, which
  already uses `skip` / `count`).

### 4.3 Cache the canonical tree (#11)

This step is optional. Do it last in the phase, and defer it if the phase runs long.

- Fix `update_jurisdiction` first: it rewrites descendants' `path` / `name_path` without
  touching their `updated_at`. Set `updated_at` on every rewritten descendant.
- Cache key: `(count(*), max(updated_at))` from `jurisdiction`, which is one cheap query.
  A module-level dict maps that key to a `jq.TreeIndex` built in canonical order. The key
  comes from the DB, so it's still correct with several workers.
- To use the cache for `sort_by=enabled`, the sort has to move from SQL to Python. Add
  `TreeIndex.sorted_children(sort_by, sort_dir, sel)`. It sorts by enabled and then by
  lowercase name and `sort_order`, which matches today's SQL. Add tests in
  `test_jurisdiction_query.py` that compare it to the SQL order for name and enabled,
  asc and desc, in both scopes.
- `GET /jurisdictions/tree`: return an `ETag` built from the same key, and honor
  `If-None-Match` with a 304.

---

## Phase 5: Low items

| Item | Change |
|---|---|
| Trailing slashes | One canonical form without slashes. Declare collection routes as `""` under their prefix: `/users`, `/companies`, `/jurisdictions`, `/private/users`, `/reset-password`, `/utils/health-check`. Update `compose.yml:37` (healthcheck URL). `.github/workflows/test-docker-compose.yml:26` already has no slash. Keep FastAPI's default `redirect_slashes` so old URLs 307 to the new ones. Note that the redirect won't carry the auth header across origins, which is fine because the client is regenerated. |
| `"subject:"` header | `login.py:149`: rename to `X-Email-Subject`. Strip non-latin-1 characters or RFC 2047-encode the value so a project name with non-ASCII characters can't break the response. |
| `/private/users` dup email → 500 | Route it through `crud.create_user` instead of building `User` by hand, with a `get_user_by_email` check first → 409 `email_taken`. `PrivateUserCreate` can then become a `UserCreate` (minus `is_superuser`). `is_verified` is already gone from it. |
| "Toggle is really set" | Fixed by Phase 3: the subtree routes are replaced by `PATCH` with explicit `add_subtrees` / `remove_subtrees`, returning the resulting selection and version. |
| Moving a jurisdiction carries licenses | `JurisdictionUpdate` gains `allow_licensed_move: bool = False`. In `crud.update_jurisdiction`, when `moving` and any `CompanyJurisdiction` exists for an id with `path` starting with `db_obj.path`, raise `Conflict(code="jurisdiction_has_licenses", context={"company_count": n, "jurisdiction_count": m})` unless the flag is set. Tests cover the move being blocked, then allowed with the flag, and an unlicensed subtree moving freely. |

---

## Phase 6: docs and final verification

- README "API" table: replace the selection rows with the Phase 3 shape. Move rows / facets
  under `/views/jurisdiction-grid`. Add a short "Errors" note (envelope plus `code`), and
  a "Concurrency" note that replaces the paragraph saying "replacing the whole list makes
  a save idempotent".
- README "Next steps": remove the parts this plan delivers.
- Update `Status` at the top of this file.
- Full run: `uv run pytest`, `bash scripts/generate-client.sh`, `bunx tsc --noEmit`,
  `bun run lint`, `bunx playwright test`. Then, in the browser: toggle a subtree in both
  scopes, and in Company Admin run the confirm-disable flow. Open a second tab, change
  the license there, and confirm the first tab gets the 412 recovery path.

## Risks

- **Phase 3 is the big one.** It touches crud, three routers, the grid mutation flow and
  the e2e fixtures together. Land the backend with tests first, then the frontend in a
  separate commit within the same phase.
- **SQLite `rowcount`** on `UPDATE` is reliable with SQLAlchemy's default DBAPI. Add a
  test that asserts 412 on a stale version, so a regression shows up there rather than as
  a silent lost update.
- **Multiple uvicorn workers** are only a concern for 4.3. The cache key comes from the
  DB, so stale caches can't serve wrong data. They only cost a rebuild.
