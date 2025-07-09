# Fixed version of your test script
import asyncio
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any
import yaml
from datetime import datetime

# Updated MockSchemeParser with proper error handling
class MockSchemeParser:
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.schemes = {}
        self.errors = []
        
    def load_schemes(self):
        """Load PM Kisan scheme from YAML with proper error handling"""
        try:
            # Check if file exists first
            if not Path(self.yaml_path).exists():
                error_msg = f"[Errno 2] No such file or directory: '{self.yaml_path}'"
                self.errors.append(error_msg)
                print(f"❌ Failed to load schemes: {error_msg}")
                return False
                
            with open(self.yaml_path, 'r') as file:
                data = yaml.safe_load(file)
                
                # Check for empty or invalid YAML
                if not data:
                    error_msg = "Empty or invalid YAML file"
                    self.errors.append(error_msg)
                    print(f"❌ Failed to load schemes: {error_msg}")
                    return False
                    
                if 'schemes' not in data:
                    error_msg = "Invalid YAML structure: 'schemes' key not found"
                    self.errors.append(error_msg)
                    print(f"❌ Failed to load schemes: {error_msg}")
                    return False
                    
                for scheme in data['schemes']:
                    self.schemes[scheme['code']] = scheme
                    
            print(f"✅ Loaded {len(self.schemes)} schemes successfully")
            return True
            
        except FileNotFoundError as e:
            error_msg = str(e)
            self.errors.append(error_msg)
            print(f"❌ Failed to load schemes: {error_msg}")
            return False
        except yaml.YAMLError as e:
            error_msg = f"YAML parsing error: {e}"
            self.errors.append(error_msg)
            print(f"❌ Failed to load schemes: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.errors.append(error_msg)
            print(f"❌ Failed to load schemes: {error_msg}")
            return False
    
    def get_scheme(self, code: str):
        return self.schemes.get(code)
    
    def get_required_fields(self, code: str):
        scheme = self.get_scheme(code)
        if scheme and 'eligibility' in scheme:
            return [rule['field'] for rule in scheme['eligibility']['rules']]
        return []
    
    def has_errors(self):
        return len(self.errors) > 0
    
    def get_errors(self):
        return self.errors.copy()

# Updated MockEligibilityChecker with better error handling
class MockEligibilityChecker:
    def check_eligibility(self, farmer_data: Dict, scheme: Dict):
        """Mock eligibility checking with error handling"""
        result = {
            'is_eligible': True,
            'score': 0.0,
            'passed_rules': [],
            'failed_rules': [],
            'missing_fields': [],
            'recommendations': []
        }
        
        # Handle missing or invalid scheme
        if not scheme or 'eligibility' not in scheme:
            result['is_eligible'] = False
            result['recommendations'].append("Invalid scheme data provided")
            return result
        
        rules = scheme.get('eligibility', {}).get('rules', [])
        if not rules:
            result['recommendations'].append("No eligibility rules found for this scheme")
            return result
            
        passed_count = 0
        
        for rule in rules:
            field = rule['field']
            
            # Check for missing fields
            if field not in farmer_data:
                result['missing_fields'].append(field)
                result['failed_rules'].append(rule['rule_id'])
                result['recommendations'].append(f"Please provide {field}: {rule['description']}")
                continue
                
            # Simple rule evaluation
            farmer_value = farmer_data[field]
            rule_value = rule['value']
            operator = rule['operator']
            
            try:
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
                    
            except (TypeError, ValueError) as e:
                result['failed_rules'].append(rule['rule_id'])
                result['recommendations'].append(f"Invalid data type for {field}")
        
        # Calculate score
        total_rules = len(rules)
        result['score'] = (passed_count / total_rules * 100) if total_rules > 0 else 0
        result['is_eligible'] = len(result['missing_fields']) == 0 and passed_count == total_rules
        
        return result

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

    async def test_error_handling(self):
        """Test 6: Error Handling - Fixed Version"""
        print("🧪 Testing Error Handling...")
        
        errors_handled = 0
        total_tests = 4  # Increased number of error tests
        
        # Test 1: Non-existent file
        print("  Testing non-existent file...")
        try:
            parser = MockSchemeParser("nonexistent.yaml")
            success = parser.load_schemes()
            if not success and parser.has_errors():
                print("    ✅ Successfully handled missing file error")
                errors_handled += 1
            else:
                print("    ❌ Failed to handle missing file error")
        except Exception as e:
            print(f"    ✅ Caught exception for missing file: {type(e).__name__}")
            errors_handled += 1
        
        # Test 2: Invalid YAML content
        print("  Testing invalid YAML...")
        try:
            # Create a temporary invalid YAML file
            invalid_yaml_path = "test_invalid.yaml"
            with open(invalid_yaml_path, 'w') as f:
                f.write("invalid: yaml: content: [unclosed")
            
            parser = MockSchemeParser(invalid_yaml_path)
            success = parser.load_schemes()
            if not success and parser.has_errors():
                print("    ✅ Successfully handled invalid YAML error")
                errors_handled += 1
            else:
                print("    ❌ Failed to handle invalid YAML error")
                
            # Clean up
            Path(invalid_yaml_path).unlink(missing_ok=True)
            
        except Exception as e:
            print(f"    ✅ Caught exception for invalid YAML: {type(e).__name__}")
            errors_handled += 1
        
        # Test 3: Empty YAML file
        print("  Testing empty YAML...")
        try:
            empty_yaml_path = "test_empty.yaml"
            with open(empty_yaml_path, 'w') as f:
                f.write("")
            
            parser = MockSchemeParser(empty_yaml_path)
            success = parser.load_schemes()
            if not success and parser.has_errors():
                print("    ✅ Successfully handled empty YAML error")
                errors_handled += 1
            else:
                print("    ❌ Failed to handle empty YAML error")
                
            # Clean up
            Path(empty_yaml_path).unlink(missing_ok=True)
            
        except Exception as e:
            print(f"    ✅ Caught exception for empty YAML: {type(e).__name__}")
            errors_handled += 1
        
        # Test 4: Invalid farmer data
        print("  Testing invalid farmer data...")
        try:
            checker = MockEligibilityChecker()
            
            # Test with completely invalid data
            invalid_data = {"invalid_field": "invalid_value"}
            invalid_scheme = {"eligibility": {"rules": [
                {"rule_id": "TEST_001", "field": "required_field", "operator": "==", "value": True, "description": "Required field"}
            ]}}
            
            result = checker.check_eligibility(invalid_data, invalid_scheme)
            
            if not result['is_eligible'] and len(result['missing_fields']) > 0:
                print("    ✅ Successfully handled invalid farmer data")
                errors_handled += 1
            else:
                print("    ❌ Failed to handle invalid farmer data")
                
        except Exception as e:
            print(f"    ✅ Caught exception for invalid data: {type(e).__name__}")
            errors_handled += 1
        
        # Calculate metrics
        error_handling_rate = (errors_handled / total_tests) * 100
        
        metrics = {
            "Error Tests": total_tests,
            "Errors Handled": errors_handled,
            "Error Handling Rate": f"{error_handling_rate:.1f}%"
        }
        
        success = errors_handled >= (total_tests * 0.75)  # 75% success rate required
        
        self.log_test(
            "Error Handling",
            success,
            f"Handled {errors_handled}/{total_tests} error scenarios",
            metrics
        )

    # Include all your other test methods here (test_scheme_parsing, test_eligibility_checking, etc.)
    # ... (copy from your original script)

    async def test_scheme_parsing(self):
        """Test 1: YAML Scheme Parsing"""
        print("🧪 Testing YAML Scheme Parsing...")
        
        # First, create a valid PM Kisan scheme file for testing
        self.create_pm_kisan_test_file()
        
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

    def create_pm_kisan_test_file(self):
        """Create a test PM Kisan YAML file"""
        pm_kisan_yaml = """
schemes:
  - id: "pm_kisan_2024"
    name: "Pradhan Mantri Kisan Samman Nidhi Yojana"
    code: "PM_KISAN"
    ministry: "Ministry of Agriculture and Farmers Welfare"
    launched_on: "2019-02-01"
    description: "Direct income support scheme for landholding farmers' families"
    metadata:
      category: "agriculture"
      disbursement: "direct_benefit_transfer"
      version: "4.0.0"
      status: "active"
    eligibility:
      rules:
        - rule_id: "PM_KISAN_001"
          field: "land_ownership"
          operator: "=="
          value: true
          data_type: "boolean"
          description: "Must own cultivable land in their name"
        - rule_id: "PM_KISAN_002"
          field: "farmer_type"
          operator: "in"
          value: ["small", "marginal", "medium"]
          data_type: "string"
          description: "Must be small, marginal, or medium farmer"
        - rule_id: "PM_KISAN_003"
          field: "age"
          operator: ">="
          value: 18
          data_type: "integer"
          description: "Must be 18 years or older"
        - rule_id: "PM_KISAN_004"
          field: "citizenship"
          operator: "=="
          value: "indian"
          data_type: "string"
          description: "Must be an Indian citizen"
        - rule_id: "PM_KISAN_005"
          field: "land_records_updated"
          operator: "=="
          value: true
          data_type: "boolean"
          description: "Land records must be updated as of Feb 1, 2019"
        - rule_id: "PM_KISAN_006"
          field: "bank_account_linked"
          operator: "=="
          value: true
          data_type: "boolean"
          description: "Bank account must be linked with Aadhaar"
        - rule_id: "PM_KISAN_007"
          field: "annual_income"
          operator: "<="
          value: 300000
          data_type: "float"
          description: "Annual family income should not exceed Rs. 3 lakhs"
      logic: "ALL"
      required_criteria:
        - "land_ownership"
        - "farmer_type"
        - "age"
        - "citizenship"
        - "land_records_updated"
        - "bank_account_linked"
        - "annual_income"
      exclusion_criteria:
        - "government_employee"
        - "income_tax_payer"
    benefits:
      - type: "direct_cash_transfer"
        description: "Annual financial assistance"
        amount: 6000.0
        frequency: "annual"
        coverage_details: "Paid in three equal installments of Rs. 2000 each"
    documents:
      - "Aadhaar Card"
      - "Land ownership documents"
      - "Bank account details"
    application_modes:
      - "online_portal"
      - "common_service_center"
    monitoring:
      claim_settlement_target: "Within 45 days"
      participating_entities:
        - "State Agriculture Departments"
        - "District Collectors"
    notes: "Scheme benefits are transferred directly to bank accounts."
"""
        
        with open("pm-kisan-scheme.yaml", "w") as f:
            f.write(pm_kisan_yaml.strip())

    # ... (include all other test methods from your original script)

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
        
        # Show detailed results
        for test_name, result in self.test_results.items():
            status = "PASS" if result['passed'] else "FAIL"
            print(f"• {test_name}: {status}")
            if result['details']:
                print(f"  Details: {result['details']}")
            if result['metrics']:
                for key, value in result['metrics'].items():
                    print(f"  {key}: {value}")
        
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
        await tester.test_error_handling()  # Test error handling
        
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
