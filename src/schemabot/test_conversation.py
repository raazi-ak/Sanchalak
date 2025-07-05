#!/usr/bin/env python3
"""
Simple test script for schemabot LLM conversation with canonical YAML integration
"""

import asyncio
import sys
from pathlib import Path

print("🔧 Starting test script...")

# Add the schemabot core to path
sys.path.append(str(Path(__file__).parent / "core"))

print("📁 Added core to path")

from core.prompts.dynamic_engine import DynamicPromptEngine, ConversationContext
from core.scheme.parser import SchemeParser
from core.eligibility.checker import EligibilityChecker

print("✅ All imports successful")

async def test_conversation():
    """Test the LLM conversation flow"""
    
    print("🚀 Starting schemabot conversation test...")
    
    try:
        # Initialize components
        print("📋 Initializing components...")
        
        # Initialize scheme parser (updated path)
        scheme_parser = SchemeParser(
            schemes_directory="src/schemabot",
            registry_file="schemas/schemes_registry.yaml"
        )
        
        print("✅ Scheme parser initialized")
        
        # Initialize eligibility checker (simplified)
        eligibility_checker = EligibilityChecker()
        
        print("✅ Eligibility checker initialized")
        
        # Initialize dynamic prompt engine
        prompt_engine = DynamicPromptEngine(scheme_parser, eligibility_checker)
        
        print("✅ Dynamic prompt engine initialized")
        
        print("✅ Components initialized successfully!")
        
        # Test initial prompt generation
        print("\n🎯 Testing initial prompt generation for PM-KISAN...")
        
        initial_prompt, context = await prompt_engine.generate_initial_prompt("PM-KISAN")
        
        print(f"📝 Initial Prompt:")
        print(f"{'='*50}")
        print(initial_prompt)
        print(f"{'='*50}")
        
        # Test conversation flow
        print("\n💬 Testing conversation flow...")
        
        # Simulate user responses
        test_responses = [
            "My name is Ram Kumar Singh",
            "I am 45 years old", 
            "I own 2.5 acres of land",
            "Yes, I have a bank account",
            "My Aadhaar is linked"
        ]
        
        current_context = context
        
        for i, user_input in enumerate(test_responses, 1):
            print(f"\n👤 User {i}: {user_input}")
            
            response = await prompt_engine.generate_followup_prompt(current_context, user_input)
            
            print(f"🤖 Assistant {i}: {response}")
            print(f"📊 Collected data: {current_context.collected_data}")
            
            if current_context.eligibility_result:
                print(f"✅ Eligibility check completed!")
                break
        
        print("\n🎉 Conversation test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🏁 Main block reached")
    asyncio.run(test_conversation())
    print("�� Script completed") 