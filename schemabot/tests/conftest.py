"""
Production-grade pytest configuration for Sanchalak testing.
Provides fixtures, test database setup, and testing utilities.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.redis import RedisContainer

from app.config import Settings, get_settings
from app.main import fastapi_app
from core.utils.cache import CacheManager
from core.utils.logger import get_logger

# Test logger
log = get_logger(__name__)

# Test configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_REDIS_URL = "redis://localhost:6379/15"  # Use different DB for tests


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure async backend for pytest-asyncio."""
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Test-specific configuration settings."""
    return Settings(
        environment="testing",
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        log_level="DEBUG",
        enable_metrics=False,
        rate_limit_enabled=False,
        cache_ttl=60,
        llm_timeout=10.0,
        max_conversation_turns=20,
    )


@pytest.fixture
def override_settings(test_settings: Settings) -> Generator[Settings, None, None]:
    """Override app settings for testing."""
    fastapi_app.dependency_overrides[get_settings] = lambda: test_settings
    yield test_settings
    fastapi_app.dependency_overrides.clear()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    """Docker Redis container for integration tests."""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis


@pytest.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Redis client for testing."""
    redis = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await redis.flushdb()  # Clear test database
    yield redis
    await redis.flushdb()
    await redis.close()


@pytest.fixture
async def cache_manager(redis_client: Redis) -> CacheManager:
    """Cache manager with test Redis client."""
    return CacheManager(redis_client=redis_client)


# ============================================================================
# HTTP Client Fixtures
# ============================================================================

@pytest.fixture
def client(override_settings: Settings) -> Generator[TestClient, None, None]:
    """Synchronous test client."""
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
async def async_client(override_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous test client."""
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Mock LLM client for testing."""
    client = MagicMock()
    client.generate_response = AsyncMock(return_value={
        "content": "Test response",
        "tokens": 10,
        "confidence": 0.95,
        "processing_time": 0.5
    })
    return client


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    return redis


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_schemes_dir() -> Generator[Path, None, None]:
    """Temporary directory with test scheme files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        schemes_dir = Path(tmpdir)
        
        # Create test scheme files
        (schemes_dir / "pm_kisan.yaml").write_text("""
code: PM_KISAN
name: PM Kisan Samman Nidhi
category: agriculture
description: Direct income support to farmers
eligibility_rules:
  - field: age 
    operator: gte
    value: 18
    data_type: integer
  - field: land_holding
    operator: lte  
    value: 2.0
    data_type: float
benefit_amount: 6000
language_support: [hi, en, bn]
        """.strip())
        
        (schemes_dir / "schemes_registry.yaml").write_text("""
schemes:
  - code: PM_KISAN
    file: pm_kisan.yaml
    status: active
    priority: 1
categories:
  - agriculture
  - pension
  - health
        """.strip())
        
        yield schemes_dir


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_farmer_data() -> Dict[str, Any]:
    """Sample farmer data for testing."""
    return {
        "name": "राम कुमार",
        "age": 35,
        "gender": "male",
        "state": "उत्तर प्रदेश",
        "district": "आगरा",
        "land_holding": 1.5,
        "income": 50000,
        "has_bank_account": True,
        "bank_account_number": "1234567890",
        "aadhaar_number": "123456789012",
        "phone_number": "+919876543210"
    }


@pytest.fixture
def sample_conversation_messages() -> list[dict]:
    """Sample conversation messages."""
    return [
        {"role": "user", "content": "मुझे PM किसान योजना के बारे में जानकारी चाहिए"},
        {"role": "assistant", "content": "मैं आपकी PM किसान योजना की पात्रता जांचने में मदद कर सकता हूं।"},
        {"role": "user", "content": "मेरी उम्र 35 साल है"},
        {"role": "assistant", "content": "धन्यवाद। आपकी कितनी जमीन है?"}
    ]


# ============================================================================
# Performance Test Fixtures
# ============================================================================

@pytest.fixture
def performance_metrics() -> dict:
    """Performance metrics tracker."""
    return {
        "requests": 0,
        "response_times": [],
        "errors": 0,
        "success_rate": 0.0
    }


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Automatic cleanup after each test."""
    yield
    # Cleanup code here if needed
    pass


# ============================================================================
# Parametrize Fixtures
# ============================================================================

@pytest.fixture(params=["hi", "en", "bn", "te", "ta"])
def supported_language(request) -> str:
    """Parametrized fixture for supported languages."""
    return request.param


@pytest.fixture(params=[
    {"age": 25, "land_holding": 1.0, "expected": True},
    {"age": 17, "land_holding": 1.0, "expected": False},
    {"age": 35, "land_holding": 3.0, "expected": False},
])
def eligibility_test_case(request) -> dict:
    """Parametrized eligibility test cases."""
    return request.param


# ============================================================================
# Markers Configuration
# ============================================================================

pytest_plugins = ["pytest_asyncio"]

# Custom markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests") 
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "redis: Tests requiring Redis")
    config.addinivalue_line("markers", "database: Tests requiring database")
    config.addinivalue_line("markers", "llm: Tests involving LLM")


# ============================================================================
# Test Collection Hook
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Modify test items during collection."""
    for item in items:
        # Add markers based on file path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
