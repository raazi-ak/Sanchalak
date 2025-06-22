"""
Service Health Monitoring
Monitors health of critical services and provides graceful degradation
"""

import asyncio
import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"

@dataclass
class ServiceHealth:
    name: str
    status: ServiceStatus
    last_check: datetime
    response_time: Optional[float] = None
    error_message: Optional[str] = None

class ServiceHealthMonitor:
    def __init__(self):
        self.services = {
            "orchestrator": "http://orchestrator:8000/health",
            "ai-agent": "http://ai-agent:8004/health", 
            "efr-db": "http://efr-db:8000/health",
            "form-filler": "http://form-filler:8000/health",
            "status-tracker": "http://status-tracker:8000/health",
            "mongo": "mongodb://admin:sanchalak123@mongo:27017"
        }
        
        self.health_cache: Dict[str, ServiceHealth] = {}
        self.cache_duration = timedelta(minutes=2)  # Cache health for 2 minutes
        
    async def check_service_health(self, service_name: str, url: str) -> ServiceHealth:
        """Check health of a single service"""
        start_time = datetime.now()
        
        try:
            if service_name == "mongo":
                # Special handling for MongoDB
                return await self._check_mongo_health(service_name)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response_time = (datetime.now() - start_time).total_seconds()
                
                if response.status_code == 200:
                    status = ServiceStatus.HEALTHY
                    error_message = None
                    logger.debug(f"✅ {service_name} is healthy ({response_time:.2f}s)")
                else:
                    status = ServiceStatus.DEGRADED
                    error_message = f"HTTP {response.status_code}"
                    logger.warning(f"⚠️ {service_name} degraded: {error_message}")
                    
        except httpx.ConnectError:
            status = ServiceStatus.DOWN
            error_message = "Connection refused"
            response_time = None
            logger.error(f"🔌 {service_name} is down: {error_message}")
            
        except httpx.TimeoutException:
            status = ServiceStatus.DOWN
            error_message = "Request timeout"
            response_time = None
            logger.error(f"⏱️ {service_name} timeout: {error_message}")
            
        except Exception as e:
            status = ServiceStatus.UNKNOWN
            error_message = str(e)
            response_time = None
            logger.error(f"❓ {service_name} unknown error: {error_message}")
        
        return ServiceHealth(
            name=service_name,
            status=status,
            last_check=datetime.now(),
            response_time=response_time,
            error_message=error_message
        )
    
    async def _check_mongo_health(self, service_name: str) -> ServiceHealth:
        """Special health check for MongoDB"""
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://admin:sanchalak123@mongo:27017", serverSelectionTimeoutMS=5000)
            client.admin.command('ismaster')
            client.close()
            
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=0.1
            )
        except Exception as e:
            return ServiceHealth(
                name=service_name,
                status=ServiceStatus.DOWN,
                last_check=datetime.now(),
                error_message=str(e)
            )
    
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all services"""
        logger.info("🔍 Checking health of all services...")
        
        tasks = []
        for service_name, url in self.services.items():
            task = self.check_service_health(service_name, url)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_status = {}
        for i, result in enumerate(results):
            service_name = list(self.services.keys())[i]
            if isinstance(result, Exception):
                health_status[service_name] = ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNKNOWN,
                    last_check=datetime.now(),
                    error_message=str(result)
                )
            else:
                health_status[service_name] = result
        
        # Cache the results
        self.health_cache = health_status
        
        # Log summary
        healthy_count = sum(1 for h in health_status.values() if h.status == ServiceStatus.HEALTHY)
        total_count = len(health_status)
        logger.info(f"📊 Service health summary: {healthy_count}/{total_count} services healthy")
        
        return health_status
    
    async def get_cached_health(self, force_refresh: bool = False) -> Dict[str, ServiceHealth]:
        """Get cached health status or refresh if needed"""
        if force_refresh or not self.health_cache or self._is_cache_expired():
            return await self.check_all_services()
        
        return self.health_cache
    
    def _is_cache_expired(self) -> bool:
        """Check if health cache has expired"""
        if not self.health_cache:
            return True
            
        oldest_check = min(h.last_check for h in self.health_cache.values())
        return datetime.now() - oldest_check > self.cache_duration
    
    def are_critical_services_healthy(self, health_status: Dict[str, ServiceHealth]) -> bool:
        """Check if critical services needed for session processing are healthy"""
        critical_services = ["orchestrator", "mongo"]
        
        for service_name in critical_services:
            if service_name not in health_status:
                return False
            
            service_health = health_status[service_name]
            if service_health.status not in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]:
                return False
        
        return True
    
    def get_system_status_message(self, health_status: Dict[str, ServiceHealth]) -> tuple[bool, str]:
        """
        Get system status and user-friendly message
        Returns: (is_available, message)
        """
        if self.are_critical_services_healthy(health_status):
            # Check if AI services are available
            ai_services = ["ai-agent", "orchestrator"]
            ai_healthy = all(
                health_status.get(service, ServiceHealth("", ServiceStatus.DOWN, datetime.now())).status 
                in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]
                for service in ai_services
            )
            
            if ai_healthy:
                return True, "✅ सभी सेवाएं उपलब्ध हैं"
            else:
                return True, "⚠️ AI सेवा में समस्या है, लेकिन आपका अनुरोध सुरक्षित रूप से संग्रहीत किया जाएगा"
        else:
            return False, "🔧 सिस्टम अस्थायी रूप से अनुपलब्ध है। आपका अनुरोध संग्रहीत किया गया है और सिस्टम वापस आने पर संसाधित होगा।"

# Global instance
health_monitor = ServiceHealthMonitor() 