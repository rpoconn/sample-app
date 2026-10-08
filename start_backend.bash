#!/usr/bin/env bash
# Sets up and starts the backend. Safe to rerun: migrations and seeding skip work already done.
set -euo pipefail

cd "$(dirname "$0")/backend"

uv sync
uv run alembic upgrade head
uv run python app/initial_data.py
uv run fastapi dev
