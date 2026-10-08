#!/usr/bin/env bash
# Builds the backend and frontend Docker images and starts both containers.
# Frontend: http://localhost:8080  Backend API: http://localhost:8000  (Ctrl+C stops both)
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed. Install Docker Desktop and try again." >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Please start Docker Desktop, then rerun this script." >&2
    exit 1
fi

APP_URL="http://localhost:8080"

open_browser() {
    case "$(uname -s)" in
        MINGW* | MSYS* | CYGWIN*) cmd.exe //c start "" "$1" ;;
        Darwin) open "$1" ;;
        *) xdg-open "$1" >/dev/null 2>&1 ;;
    esac
}

# Open the app once both the frontend and backend respond (gives up after 3 minutes)
(
    for _ in $(seq 1 180); do
        if curl -sf -o /dev/null "$APP_URL" && curl -sf -o /dev/null "http://localhost:8000/docs"; then
            echo "App is up at $APP_URL"
            open_browser "$APP_URL"
            exit 0
        fi
        sleep 1
    done
) &
WAITER_PID=$!
trap 'kill "$WAITER_PID" 2>/dev/null || true' EXIT

docker compose up --build
