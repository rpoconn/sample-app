# FastAPI Project - Backend

## Requirements

* [uv](https://docs.astral.sh/uv/) for Python package and environment management.

## Local Development

Run the backend locally. The database is a SQLite file at `backend/app.db` (set by `DATABASE_URL`).

From `./backend/`, install the dependencies, prepare the database (creates `app.db` and the first superuser), and start the development server:

```console
$ uv sync
$ uv run alembic upgrade head
$ uv run python app/initial_data.py
$ uv run fastapi dev
```

On macOS/Linux, `uv run bash scripts/prestart.sh` runs the two preparation steps. To reset the database, delete `app.db` and run them again.

The API is available at `http://localhost:8000`, with automatic interactive docs at `http://localhost:8000/docs`.

## General Workflow

Run backend commands from `./backend/` with `uv run`. Make sure your editor uses the Python interpreter in the project root's `.venv` (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on macOS/Linux).

### Code Layout

The code in `./backend/app/` is organized by business domain first, and by kind of code within each domain:

```
app/
  main.py            FastAPI app and error handlers
  api.py             mounts every domain's router
  tables.py          imports every table module, for Alembic
  seed.py            first-run data: superuser, jurisdictions, sample plan
  core/              shared: config, db engine, errors, schemas, generic deps
  auth/              login, tokens, password reset, current-user deps
  users/             accounts
  companies/         tenants and their admins
  jurisdictions/     the jurisdiction tree
    grid/            the grid view: filtering, facets, paging
  selections/        company and user opt-ins, versions, change previews
  mail/              email rendering and sending
  internal/          health check, service-to-service and dev-only routes
```

A domain package holds the files it needs out of `<domain>_models.py` (tables and API schemas), `<domain>_service.py` (business logic), `<domain>_deps.py` (FastAPI dependencies) and `<domain>_routes.py` (endpoints), prefixed with the singular domain name so every file name is unique (for example `users/user_models.py`, `companies/company_service.py`, `jurisdictions/grid/grid_routes.py`). When a service grows past one use case, or about 200 lines, it becomes a `<domain>_service/` package with one module per use case (for example `selections/selection_service/` has `selection_reading.py`, `writing.py`, `versions.py` and `impact.py`). Its `__init__.py` re-exports the public functions, so routes call `selection_service.apply_change(...)`. Inside the domains, import from the concrete module, not the package, to keep import cycles out.

A new table module must also be imported in `app/tables.py`. Tests mirror the layout under `./backend/tests/` with the same prefixes (`tests/users/test_user_service.py`), with shared builders in `tests/utils/factories.py`.

## VS Code

There are already configurations in place to run the backend through the VS Code debugger, so that you can use breakpoints, pause and explore variables, etc. **Backend: Debug FastAPI** syncs dependencies, migrates and seeds the database, then starts the server. See [../development.md](../development.md#vs-code) for the full list.

The setup is also already configured so you can run the tests through the VS Code Python tests tab.

## Backend Tests

To test the backend from the `backend` directory, run:

```console
$ uv run bash scripts/test.sh
```

The tests run with Pytest. Modify existing tests or add new ones in `./backend/tests/`.

If you use GitHub Actions, the tests will run automatically.

Extra arguments are forwarded to `pytest`. For example, to stop on the first error:

```console
$ uv run bash scripts/test.sh -x
```

### Test Coverage

When the tests run, they generate `htmlcov/index.html`. Open it in your browser to inspect the test coverage.

## Migrations

Make sure you create a revision of your models and upgrade the database with that revision every time you change them. From the `backend` directory, use `uv` to run Alembic against the SQLite database:

* Alembic is already configured to import your SQLModel models through `./backend/app/tables.py`.

* After changing a model (for example, adding a column), create a revision:

```console
$ uv run alembic revision --autogenerate -m "Add column last_name to User model"
```

* Commit to the git repository the files generated in the alembic directory.

* After creating the revision, run the migration in the database (this is what will actually change the database):

```console
$ uv run alembic upgrade head
```

If you don't want to use migrations at all, add this to `init_db()` in `./backend/app/seed.py`:

```python
SQLModel.metadata.create_all(engine)
```

and comment the line in the file `scripts/prestart.sh` that contains:

```console
$ alembic upgrade head
```

If you don't want to start with the default models and want to remove them / modify them, from the beginning, without having any previous revision, you can remove the revision files (`.py` Python files) under `./backend/app/alembic/versions/`. And then create a first migration as described above.

## Email Templates

The email templates are written with [React Email](https://react.email) in `./packages/react-email/`. The `emails` directory holds one component per email and the `ui` directory holds the shared components (layout, heading, button, link, callout).

The rendered HTML in `./backend/app/mail/templates/` is generated from those components. It is what the application sends and should not be edited by hand.

To preview the emails while editing them, start the dev server from the root of the project:

```console
$ bun run email:dev
```

Values coming from the backend are declared as Jinja placeholders in the component props, for example `username = "{{ username }}"`. The context for each email is built in `generate_*_email()` in `./backend/app/mail/service.py`, so a new placeholder needs to be added there too.

Once you are done, regenerate the templates used by the application:

```console
$ bun run email:export
```
