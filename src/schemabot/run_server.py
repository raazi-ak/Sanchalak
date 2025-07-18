#!/usr/bin/env python3
"""
Launch script for Sanchalak - Government Scheme Eligibility Bot
"""

import uvicorn
import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings

def main():
    """Launch the Sanchalak server."""
    settings = get_settings()
    
    print("🚀 Starting Sanchalak - Government Scheme Eligibility Bot")
    print(f"   Version: {settings.app_version}")
    print(f"   Environment: {settings.environment}")
    print(f"   LLM: {'LM Studio' if settings.llm.use_lm_studio else 'Local Gemma'}")
    if settings.llm.use_lm_studio:
        print(f"   Model: {settings.llm.model_name}")
        print(f"   LM Studio URL: {settings.llm.lm_studio_url}")
    else:
        print(f"   Model: {settings.llm.local_model_path}")
    print(f"   Schemes Directory: {settings.schemes.schemes_directory}")
    print(f"   Registry File: {settings.schemes.registry_file}")
    print()
    
    # Check if LM Studio is running (if using LM Studio)
    if settings.llm.use_lm_studio:
        try:
            import requests
            response = requests.get(f"{settings.llm.lm_studio_url}/v1/models", timeout=5)
            if response.status_code == 200:
                models = response.json()
                available_models = [model['id'] for model in models.get('data', [])]
                print(f"✅ LM Studio is running. Available models: {available_models}")
                
                if settings.llm.model_name in available_models:
                    print(f"✅ Using model: {settings.llm.model_name}")
                else:
                    print(f"⚠️  Model {settings.llm.model_name} not found. Available: {available_models}")
                    if available_models:
                        print(f"   Using first available model: {available_models[0]}")
            else:
                print(f"❌ LM Studio connection failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Cannot connect to LM Studio: {e}")
            print("   Make sure LM Studio is running and accessible at the configured URL")
            return 1
    else:
        print("✅ Using local Gemma model")
    
    # Check if scheme files exist
    registry_path = Path(settings.schemes.registry_file)
    if not registry_path.exists():
        print(f"❌ Schemes registry not found: {registry_path}")
        return 1
    
    print(f"✅ Schemes registry found: {registry_path}")
    
    # Launch the server
    print("\n🌐 Starting server...")
    print("   API Documentation: http://localhost:8000/docs")
    print("   Health Check: http://localhost:8000/api/health")
    print("   Metrics: http://localhost:8000/metrics")
    print()
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.debug,
            log_level=settings.get_log_level().lower(),
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server failed to start: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 