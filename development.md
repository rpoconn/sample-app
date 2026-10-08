# FastAPI Project - Development

## Local Development

For local development, run the FastAPI and Vite development servers locally. The database is a local SQLite file, so it doesn't need a database server. To capture emails such as password resets, also run [Mailpit](#mailpit).

From the `backend` directory, install the dependencies and prepare the database:

```bash
uv sync
uv run alembic upgrade head
uv run python app/initial_data.py
```

`alembic upgrade head` creates `backend/app.db` and applies the migrations. `initial_data.py` creates the first superuser from `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD` in `.env`. On macOS/Linux, `uv run bash scripts/prestart.sh` runs both steps.

Start the FastAPI development server:

```bash
uv run fastapi dev
```

In another terminal, from the project root, install the frontend dependencies and start the Vite development server:

```bash
bun install
bun run dev
```

Now you can open these URLs:

Frontend development server: <http://localhost:5173>

Backend API: <http://localhost:8000>

Automatic interactive API documentation with Swagger UI: <http://localhost:8000/docs>

Mailpit: <http://localhost:8025>

The frontend development server uses the backend at `http://localhost:8000`, as configured in `frontend/.env`.

### Database

The database is a SQLite file at `backend/app.db`, configured by `DATABASE_URL` in `.env` (`sqlite:///./app.db`, relative to the `backend` directory). It is ignored by git.

To reset it, stop the backend, then from the `backend` directory delete the file and prepare it again:

```bash
rm app.db
uv run alembic upgrade head
uv run python app/initial_data.py
```

On Windows PowerShell, use `Remove-Item app.db` instead of `rm app.db`.

The data persists across restarts. `initial_data.py` only creates the superuser and seeds the jurisdictions from `app/data/jurisdictions.json` when the superuser does not exist yet, so later changes to the jurisdictions are kept. Reset the database to re-seed them.

**Note**: The backend tests use their own database, `backend/test.db`, which they recreate on every run. They never touch `app.db`.

### VS Code

The workspace includes launch configurations (Run and Debug panel) and tasks (**Terminal** > **Run Task**):

* **Backend: Debug FastAPI**: syncs dependencies, migrates and seeds the database, then runs the backend under the debugger on port 8000.
* **Backend: Debug FastAPI (skip prestart)**: runs the backend under the debugger without the preparation steps.
* **Backend: Debug pytest** / **Backend: Debug current test file**: run the tests under the debugger.
* **Frontend: Chrome (starts Vite)** / **Frontend: Edge (starts Vite)**: start the Vite dev server and open the frontend in a debuggable browser.
* **Full Stack: Debug backend + frontend**: both of the above together.

Select the interpreter at `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (macOS/Linux) in the project root.

**Note**: If the project lives in a OneDrive (or similar) synced folder, the sync client can lock files in `.venv`, so a plain `uv sync` can fail with "Access is denied" when it tries to uninstall a package. The VS Code task uses `uv sync --inexact`, which never uninstalls anything, to avoid this. If it still fails, pause syncing or delete `.venv` and run `uv sync` again.

### Frontend Served by FastAPI

Build the frontend from the `frontend` directory:

```bash
bun run build
```

The build is written to `backend/app/frontend` and served by FastAPI at <http://localhost:8000>. Rebuild the frontend after making frontend changes.

## Mailpit

[Mailpit](https://mailpit.axllent.org) captures emails sent during local development instead of delivering them. Install the standalone binary (see [Mailpit installation](https://mailpit.axllent.org/docs/install/)) and run `mailpit`. The backend connects to it at `localhost:1025`, and captured emails are available at <http://localhost:8025>.

The backend tests don't need Mailpit, because they mock email sending. The Playwright password-reset test does.

## The `.env` File

The tracked `.env` file contains local development defaults, passwords, and other configuration. Its hostnames use `localhost` for processes running on your machine. Restart the backend after changing it.

Do not store deployment secrets in `.env`.

## Pre-commit Hooks and Code Linting

The project uses [prek](https://prek.j178.dev/), a modern alternative to [pre-commit](https://pre-commit.com/), for code linting and formatting.

You can find a file `.pre-commit-config.yaml` with configurations at the root of the project.

### Install `prek` to Run Automatically

`prek` is already part of the dependencies of the project.

From the project root, install the Git hook so that `prek` runs automatically before each commit:

```bash
uv run prek install -f
```

The `-f` flag forces the installation, in case there was already a `pre-commit` hook previously installed.

Now whenever you try to commit, for example with:

```bash
git commit
```

`prek` will check and format the code you are about to commit. If it modifies any files, add those files to Git again before committing.

### Run `prek` Manually

You can also run `prek` manually on all files from the project root:

```bash
uv run prek run --all-files
```
