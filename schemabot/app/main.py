"""
Main FastAPI application for Sanchalak - Government Scheme Eligibility Bot.

This module initializes the FastAPI app, configures middleware, sets up routing,
and handles application lifecycle events for the farmer scheme eligibility system.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import redis.asyncio as redis

from app.config import get_settings
from api.routes import health, schemes, conversations, eligibility
from core.scheme.parser import SchemeParser
from core.llm.gemma_client import GemmaClient

# Initialize structured logging

# Global settings
settings = get_settings()

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

STARTUP_TIME = Histogram(
    'app_startup_duration_seconds',
    'Application startup duration'
)


class SanchalakApp:
    """Main application class for Sanchalak."""

    def __init__(self):
        self.app: FastAPI = None
        self.redis_client: redis.Redis = None
        self.scheme_parser: SchemeParser = None
        self.llm_client: GemmaClient = None
        self._startup_time = time.time()

    async def initialize_dependencies(self):
        """Initialize application dependencies."""
        try:

            # Initialize Redis connection
            self.redis_client = await get_redis_client()
            await self.redis_client.ping()

            # Initialize scheme parser
            self.scheme_parser = SchemeParser(
                schemes_directory=settings.schemes.schemes_directory,
                registry_file=settings.schemes.registry_file
            )
            await self.scheme_parser.load_schemes()

            # Initialize LLM client
            self.llm_client = GemmaClient(
                model_name=settings.llm.model_name,
                model_path=settings.llm.model_path,
                device=settings.llm.device
            )
            await self.llm_client.initialize()

            # Record startup metrics
            startup_duration = time.time() - self._startup_time
            STARTUP_TIME.observe(startup_duration)

        except Exception as e:
            raise

    async def cleanup_dependencies(self):
        """Cleanup application dependencies."""

        if self.redis_client:
            await self.redis_client.close()

        if self.llm_client:
            await self.llm_client.cleanup()
# Global app instance
sanchalak_app = SanchalakApp()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    try:
        await sanchalak_app.initialize_dependencies()
        yield
    finally:
        # Shutdown
        await sanchalak_app.cleanup_dependencies()


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""

    # Setup structured logging
    setup_logging(
        level=settings.monitoring.log_level,
        format_type=settings.monitoring.log_format
    )

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=None,  # Disable default docs
        redoc_url=None,  # Disable default redoc
        openapi_url="/api/openapi.json" if not settings.is_production else None
    )

    # Store app reference
    sanchalak_app.app = app

    # Configure middleware stack (order matters!)
    configure_middleware(app)

    # Setup routes
    configure_routes(app)

    # Setup custom error handlers
    configure_error_handlers(app)

    # Setup custom endpoints
    configure_custom_endpoints(app)

    logger.info(
        "FastAPI application created",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment
    )

    return app


def configure_middleware(app: FastAPI):
    """Configure application middleware stack."""

    # Security headers (first)
    app.add_middleware(SecurityHeadersMiddleware)

    # Trusted host middleware
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Configure based on your domain
        )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.allowed_origins,
        allow_credentials=True,
        allow_methods=settings.security.allowed_methods,
        allow_headers=settings.security.allowed_headers,
    )

    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Rate limiting
    if settings.security.enable_rate_limiting:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.security.rate_limit_requests,
            redis_client=lambda: sanchalak_app.redis_client
        )

    # Request logging
    if settings.monitoring.enable_request_logging:
        app.add_middleware(RequestLoggingMiddleware)

    # Metrics collection (last)
    if settings.monitoring.enable_metrics:
        app.add_middleware(MetricsMiddleware)

    logger.info("Middleware stack configured")


def configure_routes(app: FastAPI):
    """Configure application routes."""

    # API routes
    app.include_router(
        health.router,
        prefix="/api/health",
        tags=["Health"]
    )

    app.include_router(
        schemes.router,
        prefix="/api/schemes",
        tags=["Schemes"]
    )

    app.include_router(
        conversations.router,
        prefix="/api/conversations",
        tags=["Conversations"]
    )

    app.include_router(
        eligibility.router,
        prefix="/api/eligibility",
        tags=["Eligibility"]
    )

    logger.info("API routes configured")


def configure_error_handlers(app: FastAPI):
    """Configure custom error handlers."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        logger.warning(
            "HTTP exception occurred",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "timestamp": time.time()
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.error(
            "Unexpected exception occurred",
            error=str(exc),
            path=request.url.path,
            exc_info=True
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "Internal server error",
                "status_code": 500,
                "path": str(request.url.path),
                "timestamp": time.time()
            }
        )

    logger.info("Error handlers configured")


def configure_custom_endpoints(app: FastAPI):
    """Configure custom endpoints."""

    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint with basic app info."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": settings.app_description,
            "environment": settings.environment,
            "timestamp": time.time()
        }

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Custom Swagger UI."""
        if settings.is_production:
            raise HTTPException(status_code=404, detail="Not found")

        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        """Custom ReDoc documentation."""
        if settings.is_production:
            raise HTTPException(status_code=404, detail="Not found")

        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    def custom_openapi():
        """Custom OpenAPI schema."""
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Add custom info
        openapi_schema["info"]["x-logo"] = {
            "url": "https://example.com/logo.png"
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    logger.info("Custom endpoints configured")


# Create the application instance
app = create_application()


# Health check utilities
async def check_dependencies() -> Dict[str, Any]:
    """Check the health of application dependencies."""
    health_status = {
        "redis": {"status": "unknown", "latency_ms": None},
        "llm": {"status": "unknown", "model": None},
        "schemes": {"status": "unknown", "count": 0}
    }

    # Check Redis
    try:
        start_time = time.time()
        await sanchalak_app.redis_client.ping()
        latency = (time.time() - start_time) * 1000
        health_status["redis"] = {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        health_status["redis"] = {"status": "unhealthy", "error": str(e)}

    # Check LLM
    try:
        if sanchalak_app.llm_client and sanchalak_app.llm_client.is_initialized:
            health_status["llm"] = {
                "status": "healthy",
                "model": settings.llm.model_name
            }
        else:
            health_status["llm"] = {"status": "unhealthy", "error": "Not initialized"}
    except Exception as e:
        health_status["llm"] = {"status": "unhealthy", "error": str(e)}

    # Check schemes
    try:
        if sanchalak_app.scheme_parser:
            scheme_count = len(sanchalak_app.scheme_parser.schemes)
            health_status["schemes"] = {"status": "healthy", "count": scheme_count}
        else:
            health_status["schemes"] = {"status": "unhealthy", "error": "Parser not initialized"}
    except Exception as e:
        health_status["schemes"] = {"status": "unhealthy", "error": str(e)}

    return health_status


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers if settings.is_production else 1,
        reload=settings.is_development,
        access_log=settings.monitoring.enable_request_logging,
        log_level=settings.monitoring.log_level.lower(),
        server_header=False,
        date_header=False
    )
