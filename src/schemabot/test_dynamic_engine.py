#!/usr/bin/env python3
"""
Test script for the refactored Dynamic Prompt Engine with canonical YAML integration
"""

import asyncio
import sys
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from core.prompts.dynamic_engine import DynamicPromptEngine, ConversationContext
from core.scheme.parser import SchemeParser
from core.eligibility.checker import EligibilityChecker

async def test_dynamic_engine():
    """Test the refactored dynamic prompt engine"""
    
    print("🚀 Testing refactored Dynamic Prompt Engine with canonical YAML integration...")
    
    try:
        # Initialize components
        scheme_parser = SchemeParser()
        eligibility_checker = EligibilityChecker()
        engine = DynamicPromptEngine(scheme_parser, eligibility_checker)
        
        print("✅ Dynamic Prompt Engine initialized")
        
        # Test PM-KISAN scheme
        scheme_code = "PM-KISAN"
        print(f"\n🎯 Testing conversation for {scheme_code}...")
        
        # Start conversation
        initial_prompt, context = await engine.generate_initial_prompt(scheme_code)
        
        print(f"📝 Initial Prompt:")
        print(f"{'='*60}")
        print(initial_prompt)
        print(f"{'='*60}")
        print(f"📊 Context: Stage={context.stage}, Current Field={context.current_field}")
        print(f"📋 Field Order: {context.field_order}")
        
        # Test conversation flow with user responses
        test_responses = [
            "My name is Ram Kumar Singh",
            "I am 45 years old", 
            "I own 2.5 acres of land",
            "Yes, I have a bank account and my Aadhaar is linked",
            "My annual income is Rs. 50,000",
            "I am from Uttar Pradesh"
        ]
        
        for i, user_input in enumerate(test_responses, 1):
            print(f"\n👤 User {i}: {user_input}")
            
            response = await engine.generate_followup_prompt(context, user_input)
            
            print(f"🤖 Assistant {i}: {response}")
            print(f"📊 Collected data: {context.collected_data}")
            print(f"🎭 Stage: {context.stage}")
            print(f"🎯 Current field: {context.current_field}")
            print(f"📈 Progress: {len(context.collected_data)}/{len(context.field_order)} fields")
            
            if context.stage == "eligibility_check":
                print(f"✅ Eligibility check stage reached!")
                break
        
        print("\n🎉 Dynamic engine test completed successfully!")
        
        # Show final conversation summary
        print(f"\n📋 Final Summary:")
        print(f"Total fields: {len(context.field_order)}")
        print(f"Collected fields: {list(context.collected_data.keys())}")
        print(f"Final stage: {context.stage}")
        print(f"Validation errors: {context.validation_errors}")
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_field_extraction():
    """Test field extraction capabilities"""
    
    print("\n🔍 Testing field extraction capabilities...")
    
    try:
        scheme_parser = SchemeParser()
        eligibility_checker = EligibilityChecker()
        engine = DynamicPromptEngine(scheme_parser, eligibility_checker)
        
        # Initialize canonical integration
        await engine.canonical_integration.initialize()
        
        # Test different field types
        test_cases = [
            ("age", "I am 35 years old", {"age": 35}),
            ("annual_income", "My income is Rs. 75,000 per year", {"annual_income": 75000.0}),
            ("land_size", "I have 3.5 acres of land", {"land_size": 3.5}),
            ("gender", "I am a male farmer", {"gender": "male"}),
            ("caste", "I belong to SC category", {"caste": "sc"}),
        ]
        
        for field_name, user_input, expected in test_cases:
            print(f"\n🧪 Testing {field_name}: '{user_input}'")
            
            extracted = await engine._extract_data_from_input_canonical(
                user_input, field_name, "PM-KISAN"
            )
            
            print(f"📤 Extracted: {extracted}")
            print(f"✅ Expected: {expected}")
            print(f"🎯 Match: {extracted == expected}")
        
    except Exception as e:
        print(f"❌ Error during extraction test: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_validation():
    """Test data validation"""
    
    print("\n✅ Testing data validation...")
    
    try:
        scheme_parser = SchemeParser()
        eligibility_checker = EligibilityChecker()
        engine = DynamicPromptEngine(scheme_parser, eligibility_checker)
        
        # Initialize canonical integration
        await engine.canonical_integration.initialize()
        
        # Test validation scenarios
        test_cases = [
            ("age", {"age": 150}, False),  # Invalid age
            ("age", {"age": 45}, True),    # Valid age
            ("annual_income", {"annual_income": -1000}, False),  # Negative income
            ("annual_income", {"annual_income": 50000}, True),   # Valid income
        ]
        
        for field_name, data, should_be_valid in test_cases:
            print(f"\n🧪 Testing validation for {field_name}: {data}")
            
            field_metadata = engine.canonical_integration.get_field_metadata("PM-KISAN", field_name)
            if field_metadata:
                is_valid, errors = engine._validate_extracted_data(data, field_metadata)
                print(f"📊 Valid: {is_valid}")
                print(f"❌ Errors: {errors}")
                print(f"🎯 Expected: {should_be_valid}")
            else:
                print(f"⚠️  No metadata found for {field_name}")
        
    except Exception as e:
        print(f"❌ Error during validation test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🏁 Starting comprehensive dynamic engine tests...")
    
    async def run_all_tests():
        await test_dynamic_engine()
        await test_field_extraction()
        await test_validation()
    
    asyncio.run(run_all_tests())
    print("🏁 All tests completed") 