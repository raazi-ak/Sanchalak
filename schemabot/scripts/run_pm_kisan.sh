#!/usr/bin/env bash
# Spin up dev environment, seed schema, and run full PM-KISAN test suite.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

echo "▶️  Creating Python venv..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"

echo "⬆️  Upgrading pip..."
pip install --upgrade pip wheel

echo "📦  Installing requirements..."
pip install -r "$ROOT/requirements.txt" \
            pytest pytest-asyncio pytest-cov httpx[cli] coverage

echo "🐳  Launching Redis in Docker..."
docker rm -f sanchalak-redis >/dev/null 2>&1 || true
docker run -d --name sanchalak-redis -p 6379:6379 redis:7-alpine

export SANCHALAK_REDIS_URL="redis://localhost:6379/0"
export SANCHALAK_ENV="test"

echo "🗄️  Running migrations..."
alembic -c "$ROOT/alembic.ini" upgrade head

echo "📥  Copying PM-KISAN schema into test fixture directory..."
mkdir -p "$ROOT/tests/fixtures/schemes"
cp "$ROOT/schemas/pm_kisan_standardized.yaml" "$ROOT/tests/fixtures/schemes/"

echo "✅  Executing pytest with coverage..."
pytest -q --cov=schemabot --cov-report=term-missing tests/integration/test_pmkisan.py

echo "🧹  Tidying up..."
docker stop sanchalak-redis && docker rm sanchalak-redis
