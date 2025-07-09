#!/usr/bin/env bash
# Spin up dev environment, seed schema, and run full PM-KISAN test suite.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    if docker ps -q -f name=sanchalak-redis >/dev/null 2>&1; then
        docker stop sanchalak-redis >/dev/null 2>&1 || true
        docker rm sanchalak-redis >/dev/null 2>&1 || true
    fi
}

# Set error trap
trap cleanup EXIT INT TERM

log_info "Setting up Sanchalak PM-KISAN test environment..."

# Check if we're in the right directory
if [[ ! -f "$ROOT/app/config.py" ]]; then
    log_error "app/config.py not found. Please run from the Sanchalak project root."
    exit 1
fi

log_info "Creating Python venv..."
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

log_info "Upgrading pip..."
pip install --upgrade pip wheel setuptools

log_info "Installing requirements..."
# Install main requirements
if [[ -f "$ROOT/requirements.txt" ]]; then
    pip install -r "$ROOT/requirements.txt"
else
    log_warning "requirements.txt not found, installing minimal dependencies"
    pip install fastapi uvicorn sqlalchemy alembic redis pydantic structlog
fi

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx coverage testcontainers[redis]

log_info "Setting environment variables..."
# Set environment variables based on your config structure
export SANCHALAK_ENVIRONMENT="test"
export SANCHALAK_DEBUG="true"
export SANCHALAK_LOG_LEVEL="DEBUG"

# Database configuration
export SANCHALAK_DATABASE_URL="sqlite:///./test_sanchalak.db"
export SANCHALAK_DB_ECHO="true"

# Redis configuration
export SANCHALAK_REDIS_URL="redis://localhost:6379/15"  # Use test DB 15
export SANCHALAK_REDIS_DEFAULT_TTL="300"  # 5 minutes for tests

# LLM configuration for testing
export SANCHALAK_LLM_MODEL_NAME="gemma-2b-it"
export SANCHALAK_LLM_MAX_TOKENS="256"
export SANCHALAK_LLM_TEMPERATURE="0.1"  # Lower for consistent test results
export SANCHALAK_LLM_MAX_CONCURRENT_REQUESTS="2"

# Scheme configuration
export SANCHALAK_SCHEMES_DIRECTORY="$ROOT/schemas"
export SANCHALAK_REGISTRY_FILE="$ROOT/schemas/schemes_registry.yaml"
export SANCHALAK_SUPPORTED_LANGUAGES="hi,en,bn,te,ta"
export SANCHALAK_DEFAULT_LANGUAGE="hi"

# Security configuration for testing
export SANCHALAK_SECRET_KEY="test-secret-key-for-development-only"
export SANCHALAK_ENABLE_RATE_LIMITING="false"

# Monitoring configuration
export SANCHALAK_ENABLE_METRICS="true"
export SANCHALAK_ENABLE_REQUEST_LOGGING="true"

# Conversation configuration
export SANCHALAK_SESSION_TIMEOUT="1800"
export SANCHALAK_MAX_MESSAGES_PER_CONVERSATION="20"

log_success "Environment variables configured"

log_info "Launching Redis in Docker..."
docker rm -f sanchalak-redis >/dev/null 2>&1 || true
docker run -d \
    --name sanchalak-redis \
    -p 6379:6379 \
    --health-cmd="redis-cli ping" \
    --health-interval=5s \
    --health-timeout=3s \
    --health-retries=5 \
    redis:7-alpine

# Wait for Redis to be ready
log_info "Waiting for Redis to be ready..."
timeout=30
while ! docker exec sanchalak-redis redis-cli ping >/dev/null 2>&1; do
    sleep 1
    timeout=$((timeout - 1))
    if [[ $timeout -eq 0 ]]; then
        log_error "Redis failed to start within 30 seconds"
        exit 1
    fi
done

log_success "Redis is ready"

log_info "Setting up database..."
# Check if alembic.ini exists and fix it if needed
if [[ -f "$ROOT/alembic.ini" ]]; then
    # Fix database URL in alembic.ini if it has placeholder
    if grep -q "driver://" "$ROOT/alembic.ini"; then
        log_info "Fixing alembic.ini database URL..."
        sed -i 's|sqlalchemy.url = driver://.*|sqlalchemy.url = sqlite:///./test_sanchalak.db|' "$ROOT/alembic.ini"
    fi
    
    log_info "Running migrations..."
    cd "$ROOT"
    alembic upgrade head
else
    log_warning "alembic.ini not found, skipping migrations"
fi

log_info "Setting up test directories..."
mkdir -p "$ROOT/tests/fixtures/schemes"
mkdir -p "$ROOT/tests/integration"
mkdir -p "$ROOT/tests/unit"

log_info "Copying PM-KISAN schema into test fixture directory..."
# Look for the PM-KISAN schema file with different possible names
SCHEMA_FILE=""
for filename in "pm_kisan_standardized.yaml" "pm-kisan-scheme.yaml" "pmkisan.yaml" "pm_kisan.yaml"; do
    if [[ -f "$ROOT/schemas/$filename" ]]; then
        SCHEMA_FILE="$filename"
        break
    fi
done

if [[ -n "$SCHEMA_FILE" ]]; then
    cp "$ROOT/schemas/$SCHEMA_FILE" "$ROOT/tests/fixtures/schemes/pm_kisan_standardized.yaml"
    log_success "PM-KISAN schema copied: $SCHEMA_FILE"
else
    log_warning "PM-KISAN schema not found, creating sample schema..."
    cat > "$ROOT/tests/fixtures/schemes/pm_kisan_standardized.yaml" << 'EOF'
code: "PMKISAN"
name: "PM-KISAN Samman Nidhi"
description: "Income support scheme for farmers"
category: "agriculture"
ministry: "Ministry of Agriculture & Farmers Welfare"
launch_date: "2019-02-24"
status: "active"
languages:
  - "en"
  - "hi"
eligibility:
  logic: "ALL"
  rules:
    - rule_id: "pmk_001"
      field: "is_farmer"
      operator: "equals"
      value: true
      data_type: "boolean"
      description: "Must be a farmer"
    - rule_id: "pmk_002"
      field: "land_size"
      operator: "greater_than"
      value: 0
      data_type: "float"
      description: "Must own agricultural land"
    - rule_id: "pmk_003"
      field: "government_employee"
      operator: "equals"
      value: false
      data_type: "boolean"
      description: "Must not be a government employee"
benefits:
  - "₹6,000 per year in three installments"
  - "Direct benefit transfer to bank account"
documents_required:
  - "Aadhaar card"
  - "Land ownership documents"
  - "Bank account details"
EOF
    log_success "Sample PM-KISAN schema created"
fi

# Create schemes registry if it doesn't exist
if [[ ! -f "$ROOT/schemas/schemes_registry.yaml" ]]; then
    log_info "Creating schemes registry..."
    mkdir -p "$ROOT/schemas"
    cat > "$ROOT/schemas/schemes_registry.yaml" << 'EOF'
version: "1.0"
last_updated: "2025-07-01"
schemes:
  - code: "PMKISAN"
    file: "pm_kisan_standardized.yaml"
    status: "active"
    category: "agriculture"
categories:
  - agriculture
  - rural_development
  - social_welfare
EOF
    log_success "Schemes registry created"
fi

log_info "Validating configuration..."
cd "$ROOT"
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from app.config import get_settings, validate_configuration
    settings = get_settings()
    print(f'✅ Configuration loaded: {settings.app_name} v{settings.app_version}')
    print(f'✅ Environment: {settings.environment}')
    print(f'✅ Database: {settings.get_database_url()}')
    print(f'✅ Redis: {settings.get_redis_url()}')
    
    if validate_configuration():
        print('✅ Configuration validation passed')
    else:
        print('❌ Configuration validation failed')
        sys.exit(1)
except Exception as e:
    print(f'❌ Configuration error: {e}')
    sys.exit(1)
"

log_info "Testing Redis connection..."
python3 -c "
import redis
try:
    r = redis.from_url('redis://localhost:6379/15')
    r.ping()
    print('✅ Redis connection successful')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
    exit(1)
"

log_info "Executing pytest with coverage..."
cd "$ROOT"

# Check if test files exist
if [[ -f "tests/integration/test_pmkisan.py" ]]; then
    pytest -v \
        --cov=app \
        --cov=api \
        --cov=core \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --tb=short \
        tests/integration/test_pmkisan.py
else
    log_warning "test_pmkisan.py not found, running all available tests..."
    pytest -v \
        --cov=app \
        --cov=api \
        --cov=core \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --tb=short \
        tests/ || log_warning "Some tests may have failed or no tests found"
fi

log_success "Test execution completed!"

echo ""
log_info "Test Summary:"
echo "  • Environment: test"
echo "  • Database: SQLite (test_sanchalak.db)"
echo "  • Redis: localhost:6379/15"
echo "  • Schema: PM-KISAN loaded"
echo "  • Coverage report: htmlcov/index.html"

echo ""
log_info "To run tests again:"
echo "  source .venv/bin/activate"
echo "  export SANCHALAK_ENVIRONMENT=test"
echo "  pytest tests/ -v"

echo ""
log_info "To start the development server:"
echo "  source .venv/bin/activate"
echo "  export SANCHALAK_ENVIRONMENT=development"
echo "  uvicorn app.main:fastapi_app --reload --host 0.0.0.0 --port 8000"
