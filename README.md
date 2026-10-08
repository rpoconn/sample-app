# Daptic: Jurisdiction Settings

This app lets each user choose which regulatory jurisdictions they monitor, within the set their organization has licensed. Jurisdictions outside the license stay visible but locked. The license itself is license data, not a user preference, so it is changed by Daptic staff in a second view.

![Personal jurisdictions view](img/jurisdictions.png)

It is built on the [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template): FastAPI, SQLModel and SQLite on the backend, and React, TypeScript, TanStack Router/Query and ag-grid on the frontend.

## Quick start (recommended)

Run the whole app with one script. It needs [Docker](https://docs.docker.com/get-started/get-docker/) and a bash shell. You don't need uv, Bun or Python.

Start Docker, then from the project root run:

```bash
bash start_app.bash
```

The script checks that Docker is running and asks you to start it if it isn't. Then it builds the backend and frontend images and starts both containers. The app is at http://localhost:8080 and the backend API at http://localhost:8000.

The build and startup take about 10 seconds; the first build takes longer while Docker downloads the base images. Your web browser opens to the site automatically. If the backend is still starting, the page may not load or login may fail; refresh the browser after a few seconds.

Leave the terminal open while you use the app. Press Ctrl+C to stop both containers. The Docker database lives in its own Docker volume, separate from `backend/app.db`. To reset it, run `docker compose down -v`.

Log in as described [below](#logging-in).

## Requirements

To run without Docker, install these first:

| Tool | Why |
|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Runs the backend and manages its Python packages |
| [Bun](https://bun.sh/docs/installation) | Runs the frontend and installs its packages |

You don't need to install Python yourself. The backend needs Python 3.14, and `uv sync` downloads it if it's missing. The database is SQLite, which is a file, so there is no database server to install. The root `.env` already has working local defaults.

After installing uv and Bun, open a new terminal so it picks up the updated `PATH`.

## Running locally without Docker

We recommend `bash start_app.bash` (see [Quick start](#quick-start-recommended)). Use these scripts if you can't run Docker, or want the Vite dev server with hot reload.

The start scripts are bash, so run them from a bash shell.

**Backend.** From the project root, run the start script. It installs dependencies, migrates and seeds the database, and starts the server. It's safe to rerun: seeding only happens on first setup.

```bash
bash start_backend.bash
```

**Frontend.** From the project root, in a second terminal, run the start script. It installs dependencies and starts the dev server at http://localhost:5173.  Please wait about ~10 seconds after launching the backend to start the front end.  

```bash
bash start_ui.bash
```

### Logging in

Log in as `admin@example.com` / `changethis`. This superuser stands in for a Daptic staff member, so they see **Jurisdictions** (their own selection), **Company Admin** (the seeded company's license) and **Admin** (user management). You can also sign up a new user; they join the seeded company as a company admin, so they see Jurisdictions and Company Admin.

To reset the data, stop the backend, delete `backend/app.db`, and run `bash start_backend.bash` again. More detail is in [development.md](development.md).

## What I built

### The two layers

| Layer | Who changes it | Where | Stored in |
|---|---|---|---|
| Company license | Daptic staff | Company Admin page | `companyjurisdiction` |
| Personal selection | Each user | Jurisdictions page | `userjurisdiction` |

The seed applies the PRD's plan to the default company: all of Canada, US National, every state except Wyoming and Utah, and San Francisco as the only city. Everything else (Wyoming, Utah, Los Angeles, Federal Districts, US Territories) is visible but locked.

### Data model

- **`jurisdiction`** is an adjacency list (`parent_id`) plus a materialized `path` of ancestor ids, so a whole subtree is one indexed prefix query. Each row also has `depth`, `sort_order` (keeps the source order), `name_path` (a readable breadcrumb), `code` (ISO 3166 / UN/LOCODE) and `region_type`.
- **`is_structural`** rows are grouping labels: the countries, groups such as "States", "Provinces" and "Cities", and a state that has cities (California). They can never be selected, by the API or the UI, but their select-all switch covers everything beneath them. Where a grouping is also a jurisdiction in its own right, that jurisdiction is a selectable child: "National" under each country, and "State" under California.
- **The license is enforced by the database.** A user opt-in has composite foreign keys to `(user, company)` and to `(company, jurisdiction)` in the company's license. A user can't hold a jurisdiction their company hasn't licensed, and when the company drops one, the database cascades it away from every user.

### API

All routes are under `/api/v1`. The ones that matter for this feature:

| Endpoint | Purpose |
|---|---|
| `GET {owner}/jurisdictions` | The owner's selected ids, as `{ jurisdiction_ids, count, version }`, with the version as an `ETag` |
| `PATCH {owner}/jurisdictions` | Merge a change: `add`, `remove`, `add_subtrees`, `remove_subtrees`. `add_subtrees` skips rows the company has not licensed. `If-Match` is optional |
| `PUT {owner}/jurisdictions` | Replace the whole set (rejects unlicensed or structural ids). `If-Match` required |
| `DELETE {owner}/jurisdictions` | Clear the set. `If-Match` required |
| `POST /companies/{id}/jurisdictions/preview` | What a PATCH would add and remove, and which users would lose an opt-in. Nothing is written |
| `GET /service/users/{user_id}/jurisdiction-ids` | **For other services:** a plain array of a user's ids. Authenticates with a superuser token, or with an `X-API-Key` header once you add `SERVICE_API_KEY` to `.env` (it isn't set by default). An inactive user, or a user of an inactive company, gets `[]` |
| `POST /views/jurisdiction-grid/rows` | One page of the flattened, filtered, sorted tree for the grid |
| `POST /views/jurisdiction-grid/facets` | Counts and filter options for the toolbar |
| `GET /jurisdictions/tree` | The whole tree as a flat list |

`{owner}` is `/users/me`, `/users/{user_id}` or `/companies/{company_id}`. A user's selection is limited to their company's license. Company license writes are meant for Daptic staff; today the API also accepts a company admin (see Next steps).

**Errors.** Every non-2xx response has the same body, `{ detail, code, context }`. Branch on `code` (for example `email_taken`, `version_mismatch`, `jurisdiction_has_licenses`), not on `detail`. Ids and counts go in `context`.

**Concurrency.** Each selection has a version, sent as the `ETag`. Send it back as `If-Match` and the write only lands if nobody changed the selection since you read it. Otherwise you get a 412 whose `context.version` is the current version, so re-read and retry. The Company Admin page's confirm-disable flow previews the drop, shows the affected users, then sends the PATCH with the preview's version, so a license change made in the meantime can't slip through. Dropping a company license also bumps the version of every user who lost an opt-in, as does moving a licensed jurisdiction (`PATCH /jurisdictions/{id}` with `allow_licensed_move: true`).

### Frontend

- **Tree grid.** ag-grid's infinite row model loads the flattened tree from the server 100 rows at a time. Filtering, search, sorting and expansion all run on the server, so the page doesn't need the full tree. This is aimed at the thousands of jurisdictions production has.
- **Four-state switches.** Every parent row has a select-all switch that shows on, off, mixed or locked, plus a count such as `49 / 52`. Locked means nothing under the row is licensed, so the switch is disabled and shows a lock. Locked jurisdictions are counted, so a subtree with some locked rows never shows as fully on. One click turns on everything available.
- **Locked rows** are dimmed and carry a lock icon whose tooltip links to Daptic support for adding jurisdictions to the license. The disabled switch's tooltip says it isn't in the license. For members, it also offers a pre-filled email asking their company admins to enable it; for company admins, it links to a Daptic sales associate.
- **Finding things.** There is search by name or code with match highlighting, status tabs (All / Enabled / Available / Disabled), and country, state and city filters.
- **"View selection"** opens a panel listing every jurisdiction that is on, each with its flag, code and parent path.

  ![Selection panel](img/selection.png)

- **Company Admin** is where Daptic staff edit a company's license. It uses the same grid against the license, with a per-row count of users who opted in. Turning off something users rely on opens a confirmation that lists exactly who will lose it.

  ![Company admin view](img/company-admin.png)

## Tests

```bash
# Backend: pytest, from backend/
uv run pytest

# End to end: Playwright, from frontend/, with the backend running (it starts Vite if needed)
bunx playwright install chromium   # first time only
bunx playwright test jurisdictions
```

`frontend/tests/jurisdictions.spec.ts` covers the feature end to end. Each test creates its own company with the PRD plan and its own users, so tests can change licenses and run in parallel without affecting each other.

- **User view:** locked versus selectable rows, saving a single jurisdiction (checked again after a reload and through the API), select-all for a subtree with and without locked rows, the selection panel listing every pick (even under a fully-on parent), search and status filters, expand and collapse all, and members being kept out of Company Admin.
- **Company view:** the admin scope, dropping an unused jurisdiction, the confirmation when a member would lose one (cancel and confirm), and licensing a new jurisdiction so a member can then pick it.

## Next steps

- **Auth and tenancy.** The PRD allowed skipping auth. The template's JWT login is kept, but every user lands in one seeded company, and new users default to company *admin*. The default should be *member*, and companies need real onboarding.
- **Restrict license edits to Daptic staff.** The license is license data, so only Daptic staff should change it. The company license endpoints still accept a company admin; limit them to staff (superusers), and make Company Admin read-only for company admins.
- **Scale testing.** Paging, filtering and subtree toggles already run on the server, but nothing has been tested against a tree of thousands of rows. Load-test it and check the SQLite queries, then move to Postgres for production.
- **License changes over time.** Record who changed a company's license and when, notify users who lose an opt-in, and offer a "re-enable for everyone who had it" undo.
- **Accessibility pass.** The status tabs' accessible names come from their tooltips ("On for you. These are the jurisdictions you manage.") rather than their labels. Use `describeChild` on those tooltips, then do a full keyboard and screen-reader review of the grid.
- **Service API hardening.** Replace the single shared `SERVICE_API_KEY` with keys scoped per service, and add a bulk "ids for these users" endpoint for consumers that fan out.

## Security: what's hardened and what's left open

This is a sample app built for an interview, not a production deployment. A code review found a list of security issues. I fixed the ones that cost nothing in convenience and left the rest open on purpose, so reviewers can sign up, change licenses, reset the database and try things without getting stuck.

**Hardened:**

- **Reset tokens work once, and a password change ends old sessions.** Every user has an `auth_version`, and access tokens and reset tokens both carry it. A password reset, a password change or a superuser editing a user's password or email bumps the version, so older tokens get 401 `token_revoked`. `/me/password` returns a new token, so you stay logged in on the tab where you changed it.
- **Smaller fixes.** An ETag has to belong to the selection it's sent for. Password recovery sends its email after the response, so response timing doesn't show whether an account exists. Emails are compared case-insensitively. A duplicate email returns 409 `email_taken` instead of a 500. The service API key is compared in constant time.

**Left open on purpose:**

- **Phase 1: signups become company admins.** `POST /users/signup` puts the new user in the seeded company as an *admin*. In production, a stranger could then rewrite the company's license and every member's selections. Here it lets a reviewer sign up and use both the Jurisdictions and Company Admin pages without a superuser promoting them first. The fix is to sign people up as *member*.
- **Phase 2: the seed can run again.** `init_db` treats "no user with the `FIRST_SUPERUSER` email" as first setup. If that superuser changes their email, the next backend start creates the superuser again and resets the default company's license to the sample plan. Here that's a handy way to get the sample data back. In production, the superuser and the sample license should be seeded in two separate steps, and each should run only once.
- **No rate limiting** on login, signup or password recovery.
- **The access token is kept in `localStorage`**, not in an httpOnly cookie, and lasts 8 days.
- **Changing your own email doesn't ask for your password**, and doesn't end your other sessions.
- **The secrets are local defaults.** `.env` ships `SECRET_KEY=changethis` and a known admin password. The backend refuses to start with them unless `FASTAPI_ENV=development`, which the local `.env` sets.

## License

MIT, inherited from the Full Stack FastAPI Template.
