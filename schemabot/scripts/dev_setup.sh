#!/usr/bin/env bash
# One-shot developer bootstrap for Sanchalak.
# Creates venv, installs deps, sets env vars, and runs the API.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT_DIR/.venv"

echo ">> Creating virtualenv..."
python3 -m venv "$VENV"
# shellcheck source=/dev/null
source "$VENV/bin/activate"

echo ">> Upgrading pip + wheel..."
pip install --upgrade pip wheel

echo ">> Installing backend dependencies..."
pip install -r "$ROOT_DIR/requirements.txt"

echo ">> Exporting default env vars..."
export SANCHALAK_ENV="development"
export SANCHALAK_LOG_LEVEL="debug"
export SANCHALAK_REDIS_URL="redis://localhost:6379/0"

echo ">> Running database migrations..."
alembic upgrade head

echo ">> Starting API (http://127.0.0.1:8000)..."
exec uvicorn app.main:fastapi_app --host 0.0.0.0 --port 8000 --reload
