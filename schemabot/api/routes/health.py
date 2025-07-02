"""
Health Check Endpoints
Provides system health monitoring and status endpoints for the Sanchalak backend.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
import time
import psutil
import asyncio
from datetime import datetime, timezone

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "healthy",
        "service": "sanchalak-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check():
    """
    Readiness probe for Kubernetes.
    Checks if the service is ready to accept traffic.
    """
    checks = {}
    all_ready = True

    # Check Redis connection
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        checks["redis"] = {"status": "ready", "latency_ms": 0}
    except Exception as e:
        checks["redis"] = {"status": "not_ready", "error": str(e)}
        all_ready = False

    # Check database connection (if applicable)
    try:
        # Placeholder for database check
        checks["database"] = {"status": "ready", "latency_ms": 0}
    except Exception as e:
        checks["database"] = {"status": "not_ready", "error": str(e)}
        all_ready = False

    status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


@router.get("/live", response_model=Dict[str, Any])
async def liveness_check():
    """
    Liveness probe for Kubernetes.
    Checks if the service is alive and responding.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": time.time() - psutil.boot_time()
    }


@router.get("/metrics", response_model=Dict[str, Any])
async def health_metrics():
    """
    Detailed health metrics for monitoring and debugging.
    """
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Application metrics
        metrics_collector = get_metrics_collector()
        app_metrics = await metrics_collector.get_health_metrics()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                }
            },
            "application": app_metrics
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect health metrics"
        )


@router.get("/dependencies", response_model=Dict[str, Any])
async def dependency_check():
    """
    Check the health of external dependencies.
    """
    dependencies = {}

    # Redis dependency
    try:
        redis_client = await get_redis_client()
        start_time = time.time()
        await redis_client.ping()
        latency = (time.time() - start_time) * 1000

        dependencies["redis"] = {
            "status": "healthy",
            "latency_ms": round(latency, 2),
            "version": await redis_client.info("server")
        }
    except Exception as e:
        dependencies["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # LLM service dependency (if applicable)
    try:
        # Placeholder for LLM health check
        dependencies["llm_service"] = {
            "status": "healthy",
            "latency_ms": 0
        }
    except Exception as e:
        dependencies["llm_service"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check if all dependencies are healthy
    all_healthy = all(dep["status"] == "healthy" for dep in dependencies.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "dependencies": dependencies,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/performance", response_model=Dict[str, Any])
async def performance_metrics():
    """
    Performance metrics for the application.
    """
    try:
        metrics_collector = get_metrics_collector()
        performance_data = await metrics_collector.get_performance_metrics()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "performance": performance_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect performance metrics"
        )