"""
Configuration for schemabot
"""

import os
from pathlib import Path

# Base directory for schemabot
SCHEMABOT_BASE = Path(__file__).parent.parent

# Canonical schemes directory - can be overridden by environment variable
CANONICAL_SCHEMES_DIR = os.getenv(
    'CANONICAL_SCHEMES_DIR', 
    str(SCHEMABOT_BASE)  # Default to schemabot directory
)

# Registry file path
SCHEMES_REGISTRY_FILE = os.getenv(
    'SCHEMES_REGISTRY_FILE',
    str(SCHEMABOT_BASE / "schemas" / "schemes_registry.yaml")
)

# LLM settings
LLM_MODEL_NAME = os.getenv('LLM_MODEL_NAME', 'gemma-2b')
LLM_MODEL_PATH = os.getenv('LLM_MODEL_PATH', '')
LLM_DEVICE = os.getenv('LLM_DEVICE', 'cpu')

# API settings
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000')) 