#!/usr/bin/env bash
# Installs dependencies and starts the frontend dev server at http://localhost:5173.
set -euo pipefail

cd "$(dirname "$0")"

bun install
bun run dev
