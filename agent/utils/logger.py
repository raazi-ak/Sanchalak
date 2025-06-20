# utils/logger.py
"""
Logging utility for the Farmer AI Pipeline
Provides structured logging with configuration support
"""

import logging
import logging.handlers
import os
import sys
import functools
import time
from typing import Any, Dict, Optional
from pathlib import Path

from config import get_settings

settings = get_settings()

class LogFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def __init__(self):
        super().__init__()
        
    def format(self, record: logging.LogRecord) -> str:
        # Base format
        log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        
        # Add extra fields if present
        if hasattr(record, 'request_id'):
            log_format = f"[%(asctime)s] [%(levelname)s] [%(name)s] [req:%(request_id)s] %(message)s"
        
        if hasattr(record, 'execution_time'):
            log_format += f" [exec_time:%(execution_time).3fs]"
        
        formatter = logging.Formatter(
            log_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        return formatter.format(record)

class FarmerAILogger:
    """Enhanced logger for the Farmer AI Pipeline"""
    
    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False
    
    @classmethod
    def _initialize_logging(cls):
        """Initialize the logging configuration once"""
        if cls._initialized:
            return
            
        # Ensure log directory exists
        os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
        
        # Create root logger
        root_logger = logging.getLogger("farmer_ai")
        root_logger.setLevel(getattr(logging, settings.log_level.upper()))
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, settings.log_level.upper()))
        console_handler.setFormatter(LogFormatter())
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=settings.log_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(LogFormatter())
        root_logger.addHandler(file_handler)
        
        cls._initialized = True

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get or create a logger with the given name"""
        cls._initialize_logging()
        
        if name not in cls._loggers:
            logger = logging.getLogger(f"farmer_ai.{name}")
            cls._loggers[name] = logger
        
        return cls._loggers[name]

def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance for the given module"""
    if name is None:
        # Get the caller's module name
        frame = sys._getframe(1)
        name = frame.f_globals.get('__name__', 'unknown')
    
    # Extract just the module name without the full path
    if '.' in name:
        name = name.split('.')[-1]
    
    return FarmerAILogger.get_logger(name)

def log_execution_time(func):
    """Decorator to log function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger = get_logger(func.__module__)
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"Function {func.__name__} executed successfully",
                extra={'execution_time': execution_time}
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Function {func.__name__} failed: {str(e)}",
                extra={'execution_time': execution_time}
            )
            raise
    
    return wrapper

def log_async_execution_time(func):
    """Decorator to log async function execution time"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        logger = get_logger(func.__module__)
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"Async function {func.__name__} executed successfully",
                extra={'execution_time': execution_time}
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Async function {func.__name__} failed: {str(e)}",
                extra={'execution_time': execution_time}
            )
            raise
    
    return wrapper

class LoggerMixin:
    """Mixin class to add logging capabilities to any class"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        return get_logger(self.__class__.__name__)

# Configure uvicorn logger to use our formatter
def configure_uvicorn_logger():
    """Configure uvicorn logger to match our format"""
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    
    # Set formatters
    for handler in uvicorn_logger.handlers:
        handler.setFormatter(LogFormatter())
    
    for handler in uvicorn_access_logger.handlers:
        handler.setFormatter(LogFormatter())

# Export commonly used functions
__all__ = [
    'get_logger',
    'log_execution_time', 
    'log_async_execution_time',
    'LoggerMixin',
    'configure_uvicorn_logger'
]