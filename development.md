# FastAPI Project - Development

## Local Development

For local development, run Mailpit with Docker Compose and run the FastAPI and Vite development servers locally. The database is a local SQLite file, so it doesn't need a database server.

Start the supporting services:

```bash
docker compose up -d mailpit
```

Then, from the `backend` directory, install the dependencies and prepare the database:

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

**Note**: The backend tests use the same database and delete all users when they finish. Run `uv run python app/initial_data.py` again afterwards to recreate the superuser.

### VS Code

The workspace includes launch configurations (Run and Debug panel) and tasks (**Terminal** > **Run Task**):

* **Backend: Debug FastAPI**: starts Mailpit, syncs dependencies, migrates and seeds the database, then runs the backend under the debugger on port 8000.
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

## Full Stack with Docker Compose

To run the backend and built frontend in Docker Compose:

```bash
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

Now you can open these URLs:

Application, with the frontend and API served by FastAPI: <http://localhost:8000>

Automatic interactive API documentation with Swagger UI: <http://localhost:8000/docs>

Traefik UI, to see how the routes are being handled by the proxy: <http://localhost:8090>

Mailpit: <http://localhost:8025>

Stop a locally running FastAPI server before starting the Compose backend because both use port `8000`.

**Note**: The first time you start the stack, it might take a minute for all the services to be ready. To monitor it, use `docker compose logs`, or `docker compose logs backend` for the backend service.

## Mailpit

[Mailpit](https://mailpit.axllent.org) captures emails sent during local development instead of delivering them. The local backend connects to it at `localhost:1025`, and the Compose backend connects to the `mailpit` service. Captured emails are available at <http://localhost:8025>.

## Docker Compose Files and Environment Variables

The main `compose.yml` file contains the configuration shared by the whole stack. Docker Compose loads it automatically.

The `compose.override.yml` file adds local development settings, such as mounting the source code as a volume. Docker Compose also loads it automatically and applies it on top of `compose.yml`.

The `compose.deploy.yml` file contains the deployment-specific settings, including HTTPS and automatic certificate handling. It is explicitly combined with `compose.yml` when deploying the application.

The backend reads local settings from the `.env` file. Docker Compose also uses it for variable interpolation and passes the settings each container needs.

After changing variables, make sure you restart the stack:

```bash
docker compose watch
```

## The `.env` File

The tracked `.env` file contains local development defaults, passwords, and other configuration. Its hostnames use `localhost` for processes running on your machine. Docker Compose overrides the SMTP hostname with its Compose service name, and stores the backend's SQLite database in the `app-data` volume (`/app/data/app.db`).

Do not store deployment secrets in `.env`. Configure them as described in the [FastAPI Cloud deployment guide](./deployment.md) or the [Docker Compose deployment guide](./deployment-docker-compose.md).

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
