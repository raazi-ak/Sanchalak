import traceback
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR

from models import ErrorResponse
from config import get_settings

settings = get_settings()
logger = logging.getLogger("farmer_ai.error_handler")

# Custom Exceptions for Farmer AI Pipeline

class FarmerAIException(Exception):
    """Base exception for Farmer AI Pipeline"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class AudioProcessingError(FarmerAIException):
    """Raised when audio processing fails"""
    pass

class TranscriptionError(FarmerAIException):
    """Raised when audio transcription fails"""
    pass

class InformationExtractionError(FarmerAIException):
    """Raised when information extraction fails"""
    pass

class EligibilityCheckError(FarmerAIException):
    """Raised when eligibility checking fails"""
    pass

class VectorDatabaseError(FarmerAIException):
    """Raised when vector database operations fail"""
    pass

class WebScrapingError(FarmerAIException):
    """Raised when web scraping fails"""
    pass

class OllamaError(FarmerAIException):
    """Raised when Ollama integration fails"""
    pass

class ModelLoadError(FarmerAIException):
    """Raised when ML model loading fails"""
    pass

class ConfigurationError(FarmerAIException):
    """Raised when configuration is invalid"""
    pass

class RateLimitExceededError(FarmerAIException):
    """Raised when rate limit is exceeded"""
    pass

class AuthenticationError(FarmerAIException):
    """Raised when authentication fails"""
    pass

class AuthorizationError(FarmerAIException):
    """Raised when authorization fails"""
    pass

# Error Handler Functions

async def create_error_response(
    request: Request,
    error: Exception,
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create a standardized error response"""
    
    request_id = getattr(request.state, 'request_id', None)
    
    error_response = ErrorResponse(
        error=message,
        error_code=error_code,
        details=details,
        request_id=request_id
    )
    
    # Log the error
    logger.error(
        f"Error occurred: {message}",
        extra={
            'request_id': request_id,
            'path': request.url.path,
            'method': request.method,
            'error_type': type(error).__name__,
            'status_code': status_code,
            'user_agent': request.headers.get('user-agent'),
            'ip': request.client.host if request.client else None
        }
    )
    
    # Log full traceback in debug mode
    if settings.debug:
        logger.debug(f"Full traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.dict()
    )

# Exception Handlers

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions"""
    return await create_error_response(
        request=request,
        error=exc,
        status_code=exc.status_code,
        message=exc.detail,
        error_code="HTTP_ERROR"
    )

async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette HTTP exceptions"""
    return await create_error_response(
        request=request,
        error=exc,
        status_code=exc.status_code,
        message=str(exc.detail),
        error_code="HTTP_ERROR"
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation exceptions"""
    # Extract validation error details
    details = {
        "validation_errors": []
    }
    
    for error in exc.errors():
        details["validation_errors"].append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return await create_error_response(
        request=request,
        error=exc,
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        message="Request validation failed",
        error_code="VALIDATION_ERROR",
        details=details
    )

async def response_validation_exception_handler(request: Request, exc: ResponseValidationError) -> JSONResponse:
    """Handle response validation exceptions"""
    return await create_error_response(
        request=request,
        error=exc,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        message="Response validation failed",
        error_code="RESPONSE_VALIDATION_ERROR",
        details={"validation_errors": exc.errors()}
    )

# Custom Exception Handlers

async def farmer_ai_exception_handler(request: Request, exc: FarmerAIException) -> JSONResponse:
    """Handle custom Farmer AI exceptions"""
    status_code_map = {
        AudioProcessingError: 400,
        TranscriptionError: 400,
        InformationExtractionError: 400,
        EligibilityCheckError: 400,
        VectorDatabaseError: 500,
        WebScrapingError: 500,
        OllamaError: 500,
        ModelLoadError: 500,
        ConfigurationError: 500,
        RateLimitExceededError: 429,
        AuthenticationError: 401,
        AuthorizationError: 403,
    }
    
    status_code = status_code_map.get(type(exc), 500)
    
    return await create_error_response(
        request=request,
        error=exc,
        status_code=status_code,
        message=exc.message,
        error_code=exc.error_code or type(exc).__name__.upper(),
        details=exc.details
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions"""
    return await create_error_response(
        request=request,
        error=exc,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        error_code="INTERNAL_ERROR",
        details={"error_type": type(exc).__name__} if settings.debug else None
    )

# Exception Handler Registration

def setup_error_handlers(app: FastAPI) -> None:
    """Setup all error handlers for the FastAPI application"""
    
    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    
    # Validation exceptions
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ResponseValidationError, response_validation_exception_handler)
    
    # Custom Farmer AI exceptions
    app.add_exception_handler(FarmerAIException, farmer_ai_exception_handler)
    
    # Global exception handler (must be last)
    app.add_exception_handler(Exception, global_exception_handler)
    
    logger.info("Error handlers registered successfully")

# Error Response Helpers

def raise_audio_processing_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise an audio processing error"""
    raise AudioProcessingError(message, "AUDIO_PROCESSING_ERROR", details)

def raise_transcription_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise a transcription error"""
    raise TranscriptionError(message, "TRANSCRIPTION_ERROR", details)

def raise_extraction_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise an information extraction error"""
    raise InformationExtractionError(message, "EXTRACTION_ERROR", details)

def raise_eligibility_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise an eligibility check error"""
    raise EligibilityCheckError(message, "ELIGIBILITY_ERROR", details)

def raise_vector_db_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise a vector database error"""
    raise VectorDatabaseError(message, "VECTOR_DB_ERROR", details)

def raise_web_scraping_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise a web scraping error"""
    raise WebScrapingError(message, "WEB_SCRAPING_ERROR", details)

def raise_ollama_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise an Ollama error"""
    raise OllamaError(message, "OLLAMA_ERROR", details)

def raise_model_load_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise a model loading error"""
    raise ModelLoadError(message, "MODEL_LOAD_ERROR", details)

def raise_config_error(message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Raise a configuration error"""
    raise ConfigurationError(message, "CONFIG_ERROR", details)

def raise_rate_limit_error(message: str = "Rate limit exceeded") -> None:
    """Raise a rate limit error"""
    raise RateLimitExceededError(message, "RATE_LIMIT_ERROR")

def raise_auth_error(message: str = "Authentication failed") -> None:
    """Raise an authentication error"""
    raise AuthenticationError(message, "AUTH_ERROR")

def raise_authz_error(message: str = "Authorization failed") -> None:
    """Raise an authorization error"""
    raise AuthorizationError(message, "AUTHZ_ERROR")

# Export commonly used exceptions and functions
__all__ = [
    # Base exception
    'FarmerAIException',
    
    # Specific exceptions
    'AudioProcessingError',
    'TranscriptionError', 
    'InformationExtractionError',
    'EligibilityCheckError',
    'VectorDatabaseError',
    'WebScrapingError',
    'OllamaError',
    'ModelLoadError',
    'ConfigurationError',
    'RateLimitExceededError',
    'AuthenticationError',
    'AuthorizationError',
    
    # Setup function
    'setup_error_handlers',
    
    # Helper functions
    'raise_audio_processing_error',
    'raise_transcription_error',
    'raise_extraction_error',
    'raise_eligibility_error',
    'raise_vector_db_error',
    'raise_web_scraping_error',
    'raise_ollama_error',
    'raise_model_load_error',
    'raise_config_error',
    'raise_rate_limit_error',
    'raise_auth_error',
    'raise_authz_error'
]