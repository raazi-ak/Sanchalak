#!/usr/bin/env python3
"""
Test script to verify the pensioner mapping fix in the conversation engine.
This script simulates the conversation flow that was causing the issue.
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from schemabot.core.conversation.langgraph_engine import SimpleLangGraphEngine, ConversationState

async def test_pensioner_flow():
    """Test the pensioner conversation flow to ensure it works correctly."""
    
    print("🧪 Testing Pensioner Conversation Flow")
    print("=" * 50)
    
    # Initialize the conversation engine
    engine = SimpleLangGraphEngine()
    
    try:
        # Initialize conversation
        welcome_msg, state = await engine.initialize_conversation("pm-kisan")
        print(f"✅ Initialized: {welcome_msg[:100]}...")
        
        # Simulate the conversation flow that was causing the issue
        print("\n📝 Simulating conversation flow:")
        
        # Step 1: User says "yes" to being a pensioner
        print("\n1. User: yes (to pensioner question)")
        response, state = await engine.process_user_input("yes", state)
        print(f"   Assistant: {response}")
        
        # Check if government_post is being asked for
        if "government post" in response.lower():
            print("   ✅ Correctly asking for government post")
        else:
            print("   ❌ Not asking for government post")
            return False
        
        # Step 2: User provides government post "mts"
        print("\n2. User: mts")
        response, state = await engine.process_user_input("mts", state)
        print(f"   Assistant: {response}")
        
        # Check if monthly_pension is being asked for
        if "monthly pension" in response.lower():
            print("   ✅ Correctly asking for monthly pension amount")
        else:
            print("   ❌ Not asking for monthly pension amount")
            return False
        
        # Step 3: User provides monthly pension amount
        print("\n3. User: 8000")
        response, state = await engine.process_user_input("8000", state)
        print(f"   Assistant: {response}")
        
        # Check if the conversation moved to the next stage
        if state.stage.value in ["family_members", "special_provisions"]:
            print("   ✅ Correctly moved to next stage")
        else:
            print(f"   ❌ Still in {state.stage.value} stage")
            return False
        
        # Verify the data was collected correctly
        print(f"\n📊 Collected Data:")
        print(f"   is_pensioner: {state.exclusion_data.get('is_pensioner')}")
        print(f"   government_post: {state.exclusion_data.get('government_post')}")
        print(f"   monthly_pension: {state.exclusion_data.get('monthly_pension')}")
        
        # Check if all required pensioner fields are present
        required_pensioner_fields = ['is_pensioner', 'government_post', 'monthly_pension']
        missing_fields = [field for field in required_pensioner_fields if field not in state.exclusion_data]
        
        if not missing_fields:
            print("   ✅ All pensioner fields collected correctly")
        else:
            print(f"   ❌ Missing fields: {missing_fields}")
            return False
        
        # Check if the data is not incorrectly mapped to special provisions
        if state.special_provisions:
            print(f"   ⚠️ Special provisions contains data: {state.special_provisions}")
            # This should be empty or not contain pensioner data
            if any('pension' in str(v).lower() for v in state.special_provisions.values()):
                print("   ❌ Pensioner data incorrectly mapped to special provisions")
                return False
            else:
                print("   ✅ No pensioner data in special provisions")
        else:
            print("   ✅ Special provisions is empty (correct)")
        
        print("\n🎉 Test PASSED! Pensioner mapping fix is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_exemption_flow():
    """Test the pensioner exemption flow for Group D/MTS employees."""
    
    print("\n🧪 Testing Pensioner Exemption Flow (Group D/MTS)")
    print("=" * 50)
    
    # Initialize the conversation engine
    engine = SimpleLangGraphEngine()
    
    try:
        # Initialize conversation
        welcome_msg, state = await engine.initialize_conversation("pm-kisan")
        
        # Simulate the conversation flow for exempt pensioner
        print("\n📝 Simulating exemption flow:")
        
        # Step 1: User says "yes" to being a pensioner
        print("\n1. User: yes (to pensioner question)")
        response, state = await engine.process_user_input("yes", state)
        print(f"   Assistant: {response}")
        
        # Step 2: User provides exempt government post "Group D"
        print("\n2. User: Group D")
        response, state = await engine.process_user_input("Group D", state)
        print(f"   Assistant: {response}")
        
        # Check if monthly_pension is still being asked for (should be)
        if "monthly pension" in response.lower():
            print("   ✅ Correctly asking for monthly pension amount (even for exempt post)")
        else:
            print("   ❌ Not asking for monthly pension amount")
            return False
        
        # Step 3: User provides high monthly pension amount
        print("\n3. User: 15000")
        response, state = await engine.process_user_input("15000", state)
        print(f"   Assistant: {response}")
        
        # Check if the conversation moved to the next stage
        if state.stage.value in ["family_members", "special_provisions"]:
            print("   ✅ Correctly moved to next stage")
        else:
            print(f"   ❌ Still in {state.stage.value} stage")
            return False
        
        # Verify the data was collected correctly
        print(f"\n📊 Collected Data:")
        print(f"   is_pensioner: {state.exclusion_data.get('is_pensioner')}")
        print(f"   government_post: {state.exclusion_data.get('government_post')}")
        print(f"   monthly_pension: {state.exclusion_data.get('monthly_pension')}")
        
        # Check if exemption is correctly noted
        if "EXEMPT" in response:
            print("   ✅ Correctly noted exemption for Group D/MTS")
        else:
            print("   ❌ Did not note exemption")
            return False
        
        print("\n🎉 Exemption Test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Exemption Test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting Pensioner Mapping Fix Tests")
    print("=" * 60)
    
    # Test 1: Basic pensioner flow
    test1_passed = await test_pensioner_flow()
    
    # Test 2: Exemption flow
    test2_passed = await test_exemption_flow()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    print(f"Basic Pensioner Flow: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Exemption Flow: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED! The pensioner mapping fix is working correctly.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED! The fix may need further work.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 