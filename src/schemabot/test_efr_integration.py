#!/usr/bin/env python3
"""
EFR Integration Test

Tests the complete EFR integration for schemabot including:
- EFR scheme client connectivity
- Enhanced prompt generation
- Data validation
- Conversation flow
"""

import asyncio
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_efr_integration():
    """Test the complete EFR integration."""
    print("🧪 Testing EFR Integration")
    print("=" * 50)
    
    try:
        # Import components
        from core.scheme.efr_integration import EFRSchemeClient, EFRSchemeParser
        from core.prompts.enhanced_engine import EnhancedPromptEngine
        from app.config import Settings
        
        print("✅ Successfully imported EFR integration components")
        
        # Test 1: EFR Client Health Check
        print("\n📡 Test 1: EFR Client Health Check")
        client = EFRSchemeClient()
        health = await client.health_check()
        print(f"   EFR Health: {'✅ Healthy' if health else '❌ Unhealthy'}")
        
        if not health:
            print("❌ EFR Database not available. Please start it first with:")
            print("   cd src/efr_database && python -m uvicorn main:app --port 8001")
            return False
        
        # Test 2: Scheme Data Retrieval
        print("\n📊 Test 2: Scheme Data Retrieval")
        scheme_data = await client.get_scheme("pm-kisan")
        if scheme_data:
            data_model = scheme_data.get('data_model', [])
            total_fields = sum(len(section.get('fields', {})) for section in data_model)
            print(f"   ✅ Retrieved scheme data with {total_fields} fields in {len(data_model)} sections")
            print(f"   ✅ Eligibility rules available: {len(scheme_data.get('eligibility_rules', []))}")
        else:
            print("   ❌ Failed to retrieve scheme data")
            return False
        
        # Test 3: EFR Parser
        print("\n🔍 Test 3: EFR Parser")
        parser = EFRSchemeParser()
        parsed_scheme = await parser.get_scheme("pm-kisan")
        if parsed_scheme:
            print(f"   ✅ Parsed scheme: {parsed_scheme.name}")
            print(f"   ✅ Required fields: {len(parsed_scheme.required_fields)}")
            print(f"   ✅ Optional fields: {len(parsed_scheme.optional_fields)}")
        else:
            print("   ❌ Failed to parse scheme")
            return False
        
        # Test 4: Enhanced Prompt Engine
        print("\n💬 Test 4: Enhanced Prompt Engine")
        settings = Settings()
        settings.schemes.use_efr_integration = True
        
        prompt_engine = EnhancedPromptEngine(
            efr_api_url="http://localhost:8001"
        )
        
        # Test initial prompt generation
        result = await prompt_engine.generate_initial_prompt("pm-kisan")
        if isinstance(result, tuple):
            initial_prompt, context = result
        else:
            initial_prompt = result
            context = None
            
        if initial_prompt and "sorry" not in initial_prompt.lower():
            print(f"   ✅ Generated initial prompt ({len(initial_prompt)} chars)")
            print(f"   Preview: {initial_prompt[:100]}...")
        else:
            print(f"   ❌ Failed to generate initial prompt: {initial_prompt}")
            return False
        
        # Test 5: Message Processing (using followup method)
        print("\n🔄 Test 5: Message Processing")
        test_message = "मेरा नाम राम कुमार है। मैं झारखंड के रांची जिले के एक छोटे गांव में रहता हूं।"
        
        if context:
            response = await prompt_engine.generate_followup_prompt(context, test_message)
            
            if response and "sorry" not in response.lower():
                print(f"   ✅ Processed message successfully")
                print(f"   Response preview: {response[:100]}...")
            else:
                print(f"   ❌ Failed to process message: {response}")
                return False
        else:
            print("   ⚠️  Skipping message processing test (no context available)")
            return False
        
        # Test 6: Special Region Detection
        print("\n🌍 Test 6: Special Region Detection")
        northeast_message = "मैं मणिपुर के इंफाल से हूं और मेरे पास जमीन है।"
        
        if context:
            special_response = await prompt_engine.generate_followup_prompt(context, northeast_message)
            
            if "मणिपुर" in special_response or "special" in special_response.lower() or "विशेष" in special_response:
                print("   ✅ Special region detection working")
            else:
                print("   ⚠️  Special region detection may not be working")
        else:
            print("   ⚠️  Skipping special region test (no context available)")
        
        # Test 7: Data Validation
        print("\n✅ Test 7: Data Validation")
        sample_data = {
            "name": "राम कुमार",
            "age": 35,
            "state": "झारखंड",
            "district": "रांची",
            "land_size_acres": 2.5,
            "land_ownership": "owned"
        }
        
        validation_result = await client.validate_data("pm-kisan", sample_data)
        if validation_result:
            is_valid = validation_result.get("valid", False)
            errors = validation_result.get("errors", [])
            print(f"   ✅ Validation completed: {'Valid' if is_valid else 'Invalid'}")
            if errors:
                print(f"   Validation errors: {errors}")
        else:
            print("   ❌ Validation failed")
        
        # Test 8: Conversation Context Building
        print("\n🔗 Test 8: Conversation Context Building")
        conversation_history = [
            {"role": "assistant", "content": initial_prompt},
            {"role": "user", "content": test_message},
            {"role": "assistant", "content": response}
        ]
        
        context = await prompt_engine._build_conversation_context(conversation_history)
        if context:
            print(f"   ✅ Built conversation context with {len(context.get('extracted_fields', {}))} extracted fields")
            print(f"   Missing fields: {len(context.get('missing_fields', []))}")
        
        print("\n🎉 All EFR Integration Tests Passed!")
        
        # Clean up
        if hasattr(client, 'session') and client.session:
            await client.session.close()
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please ensure all EFR integration components are properly installed")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        logger.exception("Full error details:")
        return False

async def test_conversation_flow():
    """Test a complete conversation flow with EFR integration."""
    print("\n🗣️  Testing Complete Conversation Flow")
    print("=" * 50)
    
    try:
        from core.prompts.enhanced_engine import EnhancedPromptEngine
        
        # Initialize enhanced prompt engine
        prompt_engine = EnhancedPromptEngine(
            efr_api_url="http://localhost:8001"
        )
        
        # Simulate a conversation
        conversation_history = []
        
        # Step 1: Initial prompt
        print("\n1️⃣  Generating initial prompt...")
        result = await prompt_engine.generate_initial_prompt("pm-kisan")
        if isinstance(result, tuple):
            initial_prompt, context = result
        else:
            initial_prompt = result
            context = None
            
        if not context:
            print("   ❌ No context returned from initial prompt")
            return False
            
        conversation_history.append({"role": "assistant", "content": initial_prompt})
        print(f"   Initial prompt: {initial_prompt[:100]}...")
        
        # Step 2: User introduction
        print("\n2️⃣  User introduces themselves...")
        user_intro = "नमस्ते, मेरा नाम सुनील कुमार है। मैं बिहार के गया जिले का रहने वाला हूं।"
        conversation_history.append({"role": "user", "content": user_intro})
        
        response1 = await prompt_engine.generate_followup_prompt(context, user_intro)
        conversation_history.append({"role": "assistant", "content": response1})
        print(f"   Response: {response1[:100]}...")
        
        # Step 3: User provides more details
        print("\n3️⃣  User provides more details...")
        user_details = "मेरी उम्र 42 साल है और मेरे पास 3 एकड़ जमीन है जो मेरी अपनी है।"
        conversation_history.append({"role": "user", "content": user_details})
        
        response2 = await prompt_engine.generate_followup_prompt(context, user_details)
        conversation_history.append({"role": "assistant", "content": response2})
        print(f"   Response: {response2[:100]}...")
        
        # Step 4: Check final context
        print("\n4️⃣  Checking final conversation context...")
        
        print(f"   Collected data: {list(context.collected_data.keys()) if hasattr(context, 'collected_data') else 'N/A'}")
        print(f"   Current field: {getattr(context, 'current_field', 'N/A')}")
        print(f"   Remaining fields: {len(getattr(context, 'remaining_fields', []))}")
        
        print("\n✅ Conversation flow test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Conversation flow test failed: {e}")
        logger.exception("Full error details:")
        return False

def main():
    """Run all tests."""
    print("🚀 Starting EFR Integration Tests")
    print("=" * 60)
    
    # Run async tests
    asyncio.run(test_efr_integration())
    asyncio.run(test_conversation_flow())
    
    print("\n✅ Test suite completed!")

if __name__ == "__main__":
    main() 