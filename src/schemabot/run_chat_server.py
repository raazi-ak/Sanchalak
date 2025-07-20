#!/usr/bin/env python3
"""
Startup script for PM-KISAN Chat Data Extraction API Server
"""

import uvicorn
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

if __name__ == "__main__":
    uvicorn.run(
        "schemabot.api.chat_server:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    ) 