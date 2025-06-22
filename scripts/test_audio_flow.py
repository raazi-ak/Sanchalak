#!/usr/bin/env python3
"""
Test Script for Audio Flow in Sanchalak System
Tests the complete pipeline: Telegram Bot → Orchestrator → AI Agent
"""

import asyncio
import aiohttp
import json
import os
import sys
from pathlib import Path

# Test configuration
ORCHESTRATOR_URL = "http://localhost:8000"
AI_AGENT_URL = "http://localhost:8004"
BOT_URL = "http://localhost:8080"

async def test_ai_agent_health():
    """Test AI Agent health"""
    print("🧠 Testing AI Agent health...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{AI_AGENT_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ AI Agent is healthy: {data}")
                    return True
                else:
                    print(f"❌ AI Agent health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ AI Agent connection failed: {e}")
        return False

async def test_orchestrator_health():
    """Test Orchestrator health"""
    print("🎼 Testing Orchestrator health...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ORCHESTRATOR_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Orchestrator is healthy: {data}")
                    return True
                else:
                    print(f"❌ Orchestrator health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Orchestrator connection failed: {e}")
        return False

async def test_ai_agent_direct():
    """Test AI Agent directly with mock data"""
    print("🧪 Testing AI Agent directly with mock data...")
    
    test_payload = {
        "session_id": "test_session_001",
        "farmer_id": "test_farmer_001",
        "text_content": "मेरे पास 2 एकड़ जमीन है और मैं धान की खेती करता हूं। मुझे सरकारी योजना चाहिए।",
        "language": "hi"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{AI_AGENT_URL}/api/v1/process",
                json=test_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ AI Agent processing successful:")
                    print(f"   - Status: {data.get('status')}")
                    print(f"   - Farmer Data: {data.get('farmer_data', {}).keys()}")
                    print(f"   - Processing Time: {data.get('processing_time', 0):.2f}s")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ AI Agent processing failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ AI Agent processing error: {e}")
        return False

async def test_orchestrator_with_mock_session():
    """Test Orchestrator with mock session data"""
    print("🎭 Testing Orchestrator with mock session data...")
    
    mock_session = {
        "session_id": "test_session_002",
        "farmer_id": "test_farmer_002",
        "start_time": "2024-01-15T10:00:00",
        "messages": [
            {
                "type": "text",
                "content": "नमस्ते, मेरा नाम राजेश है।",
                "timestamp": "2024-01-15T10:01:00"
            },
            {
                "type": "text", 
                "content": "मेरे पास 3 एकड़ जमीन है और मैं गेहूं उगाता हूं।",
                "timestamp": "2024-01-15T10:02:00"
            },
            {
                "type": "text",
                "content": "मुझे PM-KISAN योजना के बारे में जानकारी चाहिए।",
                "timestamp": "2024-01-15T10:03:00"
            }
        ],
        "user_language": "hi"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ORCHESTRATOR_URL}/process_session",
                json=mock_session,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Orchestrator processing successful:")
                    print(f"   - Status: {data.get('status')}")
                    print(f"   - Eligible Schemes: {data.get('eligible_schemes', [])}")
                    print(f"   - Processing Time: {data.get('processing_time', 0):.2f}s")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Orchestrator processing failed: {response.status}")
                    print(f"   Error: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ Orchestrator processing error: {e}")
        return False

def print_telegram_testing_guide():
    """Print guide for testing with real Telegram audio"""
    print("\n" + "="*60)
    print("📱 TELEGRAM AUDIO TESTING GUIDE")
    print("="*60)
    
    print("""
🎯 **READY FOR REAL AUDIO TESTING!**

Volume sharing is now fixed. You can test with real audio:

📋 **TESTING STEPS:**

1️⃣ **Start the System:**
   ```bash
   docker-compose up -d
   ```

2️⃣ **Check Services:**
   ```bash
   docker-compose ps
   # All services should be "Up"
   ```

3️⃣ **Find Your Bot on Telegram:**
   - Search for your bot (@your_bot_name)
   - Start a conversation

4️⃣ **Test Registration:**
   ```
   /start
   # Follow registration prompts
   # Share phone number when asked
   ```

5️⃣ **Test Audio Session:**
   ```
   /start_log
   # Now record voice messages in Hindi/local language:
   # "मेरे पास 2 एकड़ जमीन है"
   # "मैं धान की खेती करता हूं"
   # "मुझे सरकारी योजना चाहिए"
   /end_log
   ```

6️⃣ **Check Processing:**
   ```
   /status
   # Should show farmer data extraction results
   ```

🎤 **AUDIO TESTING TIPS:**

- **Record in Hindi/Local Languages:** More realistic
- **Farming Content:** Mention crops, land size, problems
- **Multiple Messages:** Record 3-4 short voice messages
- **Government Schemes:** Ask about PM-KISAN, loans, etc.

📁 **FILE LOCATIONS (in containers):**
- Voice files: `/app/uploads/session_xxx_audio_1.ogg`
- Shared volume: `shared-uploads`
- All services can now access same files!

🔍 **DEBUGGING:**
   ```bash
   # Check logs
   docker logs sanchalak-telegram-bot
   docker logs sanchalak-orchestrator  
   docker logs sanchalak-ai-agent

   # Check shared volume
   docker exec sanchalak-telegram-bot ls -la /app/uploads/
   docker exec sanchalak-orchestrator ls -la /app/uploads/
   ```

🎯 **EXPECTED FLOW:**
1. You record voice → Saved to shared-uploads
2. /end_log → Orchestrator gets file paths  
3. Orchestrator → AI Agent with voice files
4. AI Agent → Whisper transcription → NLP → EFR storage
5. You get notification: "Data stored successfully"

✅ **SUCCESS INDICATORS:**
- Voice messages saved: "🎤 Voice message logged"
- Processing complete: "✅ डेटा संग्रहीत हो गया"
- EFR data stored: Check /status command
    """)

async def main():
    """Main test function"""
    print("🌾 SANCHALAK AUDIO FLOW TESTING")
    print("="*50)
    
    # Test health checks
    ai_healthy = await test_ai_agent_health()
    orchestrator_healthy = await test_orchestrator_health()
    
    if not ai_healthy or not orchestrator_healthy:
        print("\n❌ Some services are not healthy. Start the system first:")
        print("   docker-compose up -d")
        sys.exit(1)
    
    print("\n🧪 RUNNING MOCK DATA TESTS...")
    
    # Test AI Agent directly
    ai_test_passed = await test_ai_agent_direct()
    
    # Test Orchestrator
    orchestrator_test_passed = await test_orchestrator_with_mock_session()
    
    print("\n📊 TEST RESULTS:")
    print(f"   AI Agent Direct Test: {'✅ PASS' if ai_test_passed else '❌ FAIL'}")
    print(f"   Orchestrator Test: {'✅ PASS' if orchestrator_test_passed else '❌ FAIL'}")
    
    if ai_test_passed and orchestrator_test_passed:
        print("\n🎉 ALL TESTS PASSED! System is ready for audio testing.")
        print_telegram_testing_guide()
    else:
        print("\n❌ Some tests failed. Check the logs and fix issues.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 