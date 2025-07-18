class MockUser:
    user_id: str = "user123"
    username: str = "admin"

async def get_current_user():
    return MockUser()

class MockMetricsCollector:
    async def record_api_call(self, endpoint: str, count: int):
        pass

async def get_metrics_collector():
    return MockMetricsCollector()

class MockCacheManager:
    async def get(self, key):
        return None
    async def set(self, key, value, ttl=None):
        pass

async def get_cache_manager():
    return MockCacheManager()