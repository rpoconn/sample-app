# Plan: API architecture fixes

## Status

- In progress. Phases 1 (error model, list envelope), 2 (lifecycle invariants), 3 (versioned
  selection resource) and 4 (contract cleanup, `/views` namespace, tree cache) are done and
  were removed from this file. Next up is Phase 5. Findings come from the adversarial API
  review (2026-10-07).
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
  - Selections: `{owner}/jurisdictions` with GET / PUT / PATCH / DELETE and ETag / If-Match
    versioning, plus `POST companies/{id}/jurisdictions/preview`. Code is in
    `app/api/routes/selections.py`.
  - Grid view models are at `POST /views/jurisdiction-grid/rows` and `/facets`
    (`app/api/routes/views.py`). `GET /jurisdictions/tree` takes no params, returns the
    canonical order with an `ETag`, and honors `If-None-Match` (304).
  - `crud.get_canonical_tree` caches the canonical `TreeIndex`, keyed on
    `(count(*), max(updated_at))`. It serves `/tree`, facets and unsorted rows.
    **Decision:** sorted rows (`sort_by=name|enabled`) keep the SQL `ORDER BY` in
    `crud.get_jurisdiction_tree`. The sort was not moved into Python, so a sorted request
    never pulls the whole collection into the app server to reorder it.
  - `JurisdictionPublic` no longer exposes `path`, `depth` or `sort_order`.
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
- Check `alembic heads` before adding a migration; new migrations
  chain from it.
- Never hand-edit `frontend/src/client/**`. Regenerate it.

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

- **Moving a licensed jurisdiction (Phase 5)** changes what companies hold without
  touching their selection versions. If the move is allowed with the flag, decide whether
  it should bump the affected companies' and users' versions.
