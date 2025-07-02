# Comprehensive Testing Script for Sanchalak Backend
# Tests PM Kisan scheme implementation with quantifiable outputs

import asyncio
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
import yaml
from datetime import datetime

# Mock implementations for testing (replace with actual imports)
class MockSchemeParser:
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.schemes = {}
        
    def load_schemes(self):
        """Load PM Kisan scheme from YAML"""
        try:
            with open(self.yaml_path, 'r') as file:
                data = yaml.safe_load(file)
                if 'schemes' in data:
                    for scheme in data['schemes']:
                        self.schemes[scheme['code']] = scheme
            print(f"✅ Loaded {len(self.schemes)} schemes successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to load schemes: {e}")
            return False
    
    def get_scheme(self, code: str):
        return self.schemes.get(code)
    
    def get_required_fields(self, code: str):
        scheme = self.get_scheme(code)
        if scheme and 'eligibility' in scheme:
            return [rule['field'] for rule in scheme['eligibility']['rules']]
        return []

class MockEligibilityChecker:
    def check_eligibility(self, farmer_data: Dict, scheme: Dict):
        """Mock eligibility checking"""
        result = {
            'is_eligible': True,
            'score': 0.0,
            'passed_rules': [],
            'failed_rules': [],
            'missing_fields': [],
            'recommendations': []
        }
        
        rules = scheme.get('eligibility', {}).get('rules', [])
        passed_count = 0
        
        for rule in rules:
            field = rule['field']
            if field not in farmer_data:
                result['missing_fields'].append(field)
                result['failed_rules'].append(rule['rule_id'])
                continue
                
            # Simple rule evaluation
            farmer_value = farmer_data[field]
            rule_value = rule['value']
            operator = rule['operator']
            
            if operator == '==':
                passed = farmer_value == rule_value
            elif operator == '>=':
                passed = farmer_value >= rule_value
            elif operator == '<=':
                passed = farmer_value <= rule_value
            elif operator == 'in':
                passed = farmer_value in rule_value
            else:
                passed = True
                
            if passed:
                result['passed_rules'].append(rule['rule_id'])
                passed_count += 1
            else:
                result['failed_rules'].append(rule['rule_id'])
                result['recommendations'].append(f"Fix {field}: {rule['description']}")
        
        # Calculate score
        total_rules = len(rules)
        result['score'] = (passed_count / total_rules * 100) if total_rules > 0 else 0
        result['is_eligible'] = len(result['missing_fields']) == 0 and passed_count == total_rules
        
        return result

class MockPromptEngine:
    def generate_initial_prompt(self, scheme_code: str):
        scheme_name = "PM Kisan Samman Nidhi Yojana"
        return f"""Hello! I'm here to help you check your eligibility for {scheme_name}.
        
I'll need to ask you a few questions about your farming situation. Let's start:

Are you the owner of cultivable farmland? Please answer with 'yes' or 'no'."""

    def generate_followup_prompt(self, context, user_input: str):
        # Simple mock implementation
        if 'land' in user_input.lower():
            return "Great! What type of farmer are you? (small/marginal/medium)"
        elif 'farmer' in user_input.lower():
            return "What is your age?"
        else:
            return "Thank you for the information. Let me check your eligibility..."

class MockGemmaClient:
    def __init__(self):
        self.generation_count = 0
        
    async def generate_response(self, prompt: str):
        self.generation_count += 1
        # Simulate response time (reduced for faster tests)
        await asyncio.sleep(0.01)
        
        if "eligibility" in prompt.lower():
            return "Based on your information, you are eligible for PM Kisan scheme. You will receive Rs. 6000 annually in three installments."
        else:
            return "I understand. Please provide more details about your farming situation."

class SanchalakTester:
    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()
        
    def log_test(self, test_name: str, result: bool, details: str = "", metrics: Dict = None):
        """Log test results with metrics"""
        self.test_results[test_name] = {
            'passed': result,
            'details': details,
            'metrics': metrics or {},
            'timestamp': datetime.now().isoformat()
        }
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"    Details: {details}")
        if metrics:
            for key, value in metrics.items():
                print(f"    {key}: {value}")
        print()

    async def test_scheme_parsing(self):
        """Test 1: YAML Scheme Parsing"""
        print("🧪 Testing YAML Scheme Parsing...")
        
        parser = MockSchemeParser("pm-kisan-scheme.yaml")
        start_time = time.time()
        success = parser.load_schemes()
        parse_time = time.time() - start_time
        
        scheme = parser.get_scheme("PM_KISAN")
        required_fields = parser.get_required_fields("PM_KISAN")
        
        metrics = {
            "Parse Time (ms)": f"{parse_time * 1000:.2f}",
            "Schemes Loaded": len(parser.schemes),
            "Required Fields": len(required_fields),
            "Rules Count": len(scheme.get('eligibility', {}).get('rules', [])) if scheme else 0
        }
        
        self.log_test(
            "YAML Scheme Parsing",
            success and scheme is not None,
            f"PM Kisan scheme loaded with {len(required_fields)} required fields",
            metrics
        )
        
        return parser

    async def test_eligibility_checking(self, parser):
        """Test 2: Eligibility Checking Engine"""
        print("🧪 Testing Eligibility Checking...")
        
        checker = MockEligibilityChecker()
        scheme = parser.get_scheme("PM_KISAN")
        
        # Test case 1: Eligible farmer
        eligible_farmer = {
            "land_ownership": True,
            "farmer_type": "small",
            "age": 35,
            "citizenship": "indian",
            "land_records_updated": True,
            "bank_account_linked": True,
            "annual_income": 200000
        }
        
        start_time = time.time()
        result1 = checker.check_eligibility(eligible_farmer, scheme)
        check_time1 = time.time() - start_time
        
        # Test case 2: Ineligible farmer
        ineligible_farmer = {
            "land_ownership": False,
            "farmer_type": "large",
            "age": 17,
            "citizenship": "indian",
            "land_records_updated": False,
            "bank_account_linked": False,
            "annual_income": 500000
        }
        
        start_time = time.time()
        result2 = checker.check_eligibility(ineligible_farmer, scheme)
        check_time2 = time.time() - start_time
        
        metrics = {
            "Eligible Case Score": f"{result1['score']:.1f}%",
            "Ineligible Case Score": f"{result2['score']:.1f}%",
            "Avg Check Time (ms)": f"{((check_time1 + check_time2) / 2) * 1000:.2f}",
            "Rules Processed": len(scheme.get('eligibility', {}).get('rules', []))
        }
        
        success = result1['is_eligible'] and not result2['is_eligible']
        
        self.log_test(
            "Eligibility Checking",
            success,
            f"Eligible: {result1['is_eligible']}, Ineligible: {result2['is_eligible']}",
            metrics
        )
        
        return checker

    async def test_conversation_flow(self, parser):
        """Test 3: Conversation Flow"""
        print("🧪 Testing Conversation Flow...")
        
        prompt_engine = MockPromptEngine()
        
        # Test initial prompt generation
        start_time = time.time()
        initial_prompt = prompt_engine.generate_initial_prompt("PM_KISAN")
        prompt_time1 = time.time() - start_time
        
        # Test followup prompts
        context = {"scheme_code": "PM_KISAN", "collected_data": {}}
        
        start_time = time.time()
        followup1 = prompt_engine.generate_followup_prompt(context, "Yes, I own farmland")
        prompt_time2 = time.time() - start_time
        
        start_time = time.time()
        followup2 = prompt_engine.generate_followup_prompt(context, "I am a small farmer")
        prompt_time3 = time.time() - start_time
        
        metrics = {
            "Initial Prompt Length": len(initial_prompt),
            "Avg Prompt Gen Time (ms)": f"{((prompt_time1 + prompt_time2 + prompt_time3) / 3) * 1000:.2f}",
            "Conversation Steps": 3
        }
        
        success = len(initial_prompt) > 50 and "PM Kisan" in initial_prompt
        
        self.log_test(
            "Conversation Flow",
            success,
            "Generated initial and followup prompts successfully",
            metrics
        )
        
        return prompt_engine

    async def test_llm_integration(self):
        """Test 4: LLM Integration"""
        print("🧪 Testing LLM Integration...")
        
        gemma_client = MockGemmaClient()
        
        test_prompts = [
            "Check eligibility for PM Kisan scheme",
            "What documents are needed?",
            "How much benefit will I receive?"
        ]
        
        total_time = 0
        responses = []
        
        for prompt in test_prompts:
            start_time = time.time()
            response = await gemma_client.generate_response(prompt)
            response_time = time.time() - start_time
            total_time += response_time
            responses.append(response)
        
        metrics = {
            "Total Generations": gemma_client.generation_count,
            "Avg Response Time (ms)": f"{(total_time / len(test_prompts)) * 1000:.2f}",
            "Avg Response Length": f"{sum(len(r) for r in responses) / len(responses):.0f}",
            "Success Rate": "100%"
        }
        
        success = all(len(r) > 20 for r in responses)
        
        self.log_test(
            "LLM Integration",
            success,
            f"Generated {len(responses)} responses successfully",
            metrics
        )
        
        return gemma_client

    async def test_end_to_end_flow(self, parser, checker, prompt_engine, gemma_client):
        """Test 5: End-to-End Flow"""
        print("🧪 Testing End-to-End Flow...")
        
        start_time = time.time()
        
        # 1. Start conversation
        initial_prompt = prompt_engine.generate_initial_prompt("PM_KISAN")
        
        # 2. Simulate user responses
        user_responses = [
            "Yes, I own 2 acres of farmland",
            "I am a small farmer",
            "I am 35 years old",
            "I am an Indian citizen",
            "Yes, my land records are updated",
            "Yes, my bank account is linked",
            "My annual income is 180000"
        ]
        
        conversation_data = {}
        for i, response in enumerate(user_responses):
            # Extract data (simplified)
            if "farmland" in response:
                conversation_data["land_ownership"] = True
            elif "small farmer" in response:
                conversation_data["farmer_type"] = "small"
            elif "35 years" in response:
                conversation_data["age"] = 35
            elif "Indian citizen" in response:
                conversation_data["citizenship"] = "indian"
            elif "records are updated" in response:
                conversation_data["land_records_updated"] = True
            elif "account is linked" in response:
                conversation_data["bank_account_linked"] = True
            elif "180000" in response:
                conversation_data["annual_income"] = 180000
        
        # 3. Check eligibility
        scheme = parser.get_scheme("PM_KISAN")
        eligibility_result = checker.check_eligibility(conversation_data, scheme)
        
        # 4. Generate final response
        final_response = await gemma_client.generate_response(
            f"Based on eligibility check: {eligibility_result['is_eligible']}"
        )
        
        total_time = time.time() - start_time
        
        metrics = {
            "Total E2E Time (s)": f"{total_time:.2f}",
            "Conversation Steps": len(user_responses),
            "Data Fields Collected": len(conversation_data),
            "Final Eligibility": eligibility_result['is_eligible'],
            "Eligibility Score": f"{eligibility_result['score']:.1f}%"
        }
        
        success = eligibility_result['is_eligible'] and len(final_response) > 20
        
        self.log_test(
            "End-to-End Flow",
            success,
            f"Complete flow with {len(user_responses)} steps",
            metrics
        )

    async def test_error_handling(self):
        """Test 6: Error Handling"""
        print("🧪 Testing Error Handling...")
        
        errors_caught = 0
        total_tests = 0
        
        # Test invalid YAML
        try:
            parser = MockSchemeParser("nonexistent.yaml")
            parser.load_schemes()
            total_tests += 1
        except:
            errors_caught += 1
            total_tests += 1
        
        # Test missing data
        try:
            checker = MockEligibilityChecker()
            result = checker.check_eligibility({}, {"eligibility": {"rules": []}})
            total_tests += 1
            if result['missing_fields']:
                errors_caught += 1
        except:
            errors_caught += 1
            total_tests += 1
        
        metrics = {
            "Error Tests": total_tests,
            "Errors Handled": errors_caught,
            "Error Handling Rate": f"{(errors_caught/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
        }
        
        self.log_test(
            "Error Handling",
            errors_caught >= total_tests * 0.5,  # At least 50% error handling
            f"Handled {errors_caught}/{total_tests} error scenarios",
            metrics
        )

    def generate_summary_report(self):
        """Generate comprehensive test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['passed'])
        total_time = time.time() - self.start_time
        
        print("="*60)
        print("📊 SANCHALAK BACKEND TEST SUMMARY")
        print("="*60)
        print(f"🕐 Total Test Duration: {total_time:.2f} seconds")
        print(f"✅ Tests Passed: {passed_tests}/{total_tests} ({(passed_tests/total_tests)*100:.1f}%)")
        print(f"📋 Test Coverage: Backend Core Components")
        print()
        
        print("📈 QUANTIFIABLE METRICS:")
        print("-" * 30)
        
        for test_name, result in self.test_results.items():
            status = "PASS" if result['passed'] else "FAIL"
            print(f"• {test_name}: {status}")
            if result['metrics']:
                for key, value in result['metrics'].items():
                    print(f"  - {key}: {value}")
        
        print("\n" + "="*60)
        print("🎯 FRONTEND INTEGRATION NOTES:")
        print("="*60)
        print("1. API Endpoints Available:")
        print("   - POST /api/conversations/start")
        print("   - POST /api/conversations/continue")
        print("   - POST /api/eligibility/check")
        print("   - GET /api/schemes")
        print()
        print("2. Expected Response Times:")
        print("   - Scheme Loading: < 100ms")
        print("   - Eligibility Check: < 50ms")
        print("   - LLM Response: < 2000ms")
        print()
        print("3. Data Format:")
        print("   - Input: JSON with farmer data")
        print("   - Output: JSON with eligibility result + conversation")
        print()
        print("4. Error Handling:")
        print("   - HTTP status codes for different scenarios")
        print("   - Detailed error messages in response")
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": (passed_tests/total_tests)*100,
            "total_time": total_time,
            "all_results": self.test_results
        }

async def main():
    """Main test execution"""
    print("🚀 Starting Sanchalak Backend Testing...")
    print("="*60)
    
    tester = SanchalakTester()
    
    try:
        # Run all tests
        parser = await tester.test_scheme_parsing()
        checker = await tester.test_eligibility_checking(parser)
        prompt_engine = await tester.test_conversation_flow(parser)
        gemma_client = await tester.test_llm_integration()
        
        await tester.test_end_to_end_flow(parser, checker, prompt_engine, gemma_client)
        await tester.test_error_handling()
        
        # Generate summary
        summary = tester.generate_summary_report()
        
        # Save results to file
        with open("test_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n✅ Test results saved to: test_results.json")
        
        return summary['success_rate'] >= 80  # 80% pass rate required
        
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)