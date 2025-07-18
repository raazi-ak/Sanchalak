#!/usr/bin/env python3
"""
Launcher script for Sanchalak CLI Chat Interface
"""

import subprocess
import sys
import os
from pathlib import Path

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check required modules
    required_modules = ["requests", "aiohttp", "pydantic", "fastapi"]
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            missing_modules.append(module)
            print(f"❌ {module}")
    
    if missing_modules:
        print(f"\n❌ Missing modules: {', '.join(missing_modules)}")
        print("   Install with: pip install " + " ".join(missing_modules))
        return False
    
    return True

def check_services():
    """Check if required services are running."""
    print("\n🔍 Checking services...")
    
    # Check LM Studio
    try:
        import requests
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        if response.status_code == 200:
            models = response.json()
            available_models = [model['id'] for model in models.get('data', [])]
            print(f"✅ LM Studio running with models: {available_models}")
        else:
            print(f"⚠️  LM Studio connection issue: {response.status_code}")
            print("   Make sure LM Studio is running on port 1234")
            return False
    except Exception as e:
        print(f"❌ LM Studio not accessible: {e}")
        print("   Please start LM Studio on http://localhost:1234")
        return False
    
    # Check EFR Database
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ EFR Database: {health.get('status', 'unknown')}")
        else:
            print(f"❌ EFR Database not accessible: {response.status_code}")
            print("   Please start EFR database with:")
            print("   cd src/efr_database && python -m uvicorn main:app --port 8001")
            return False
    except Exception as e:
        print(f"❌ EFR Database not accessible: {e}")
        print("   Please start EFR database with:")
        print("   cd src/efr_database && python -m uvicorn main:app --port 8001")
        return False
    
    return True

def main():
    """Main launcher function."""
    print("🚀 Sanchalak CLI Chat Launcher")
    print("=" * 50)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please install missing dependencies.")
        sys.exit(1)
    
    # Check services
    if not check_services():
        print("\n❌ Required services are not running.")
        print("\nTo start the services:")
        print("1. Start LM Studio and load a model")
        print("2. Start EFR database:")
        print("   cd src/efr_database && python -m uvicorn main:app --port 8001")
        
        response = input("\nDo you want to continue anyway? (y/N): ").lower()
        if response != 'y':
            print("👋 Goodbye!")
            sys.exit(1)
    
    print("\n✅ All checks passed! Starting CLI chat...")
    print("=" * 50)
    
    # Launch the chat CLI
    try:
        script_dir = Path(__file__).parent
        chat_script = script_dir / "cli_chat.py"
        
        if not chat_script.exists():
            print(f"❌ Chat script not found: {chat_script}")
            sys.exit(1)
        
        # Run the chat CLI
        subprocess.run([sys.executable, str(chat_script)], cwd=script_dir)
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Failed to start chat: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 