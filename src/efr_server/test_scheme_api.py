#!/usr/bin/env python3
"""
Test script for the EFR Database Scheme API
Tests the OpenAPI-compliant scheme endpoints
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any

# If there are any local imports, convert them to absolute imports with src.efr_database prefix

class SchemeAPITester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.test_results = {}
        
    def test_connection(self) -> bool:
        """Test basic connection to EFR database"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print("✅ EFR Database is healthy")
                print(f"   Farmers: {health_data.get('total_farmers', 0)}")
                print(f"   Schemes loaded: {health_data.get('scheme_service_loaded', False)}")
                print(f"   Total schemes: {health_data.get('total_schemes', 0)}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def test_scheme_registry(self) -> bool:
        """Test scheme registry endpoint"""
        try:
            print("\n🧪 Testing scheme registry...")
            response = requests.get(f"{self.base_url}/api/schemes/registry")
            
            if response.status_code == 200:
                registry = response.json()
                print(f"✅ Registry retrieved successfully")
                print(f"   Version: {registry.get('version')}")
                print(f"   Total schemes: {registry.get('total_schemes', 0)}")
                print(f"   Categories: {registry.get('categories', [])}")
                print(f"   Last updated: {registry.get('last_updated')}")
                return True
            else:
                print(f"❌ Registry test failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Registry test error: {e}")
            return False
    
    def test_list_schemes(self) -> bool:
        """Test listing schemes"""
        try:
            print("\n🧪 Testing scheme listing...")
            response = requests.get(f"{self.base_url}/api/schemes")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    data = result.get('data', {})
                    schemes = data.get('schemes', [])
                    print(f"✅ Schemes listed successfully")
                    print(f"   Found {len(schemes)} schemes")
                    print(f"   Total count: {data.get('total_count', 0)}")
                    
                    if schemes:
                        scheme = schemes[0]
                        print(f"   First scheme: {scheme.get('name')} ({scheme.get('code')})")
                    
                    return True
                else:
                    print(f"❌ Scheme listing failed: {result.get('message')}")
                    return False
            else:
                print(f"❌ Scheme listing failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Scheme listing error: {e}")
            return False
    
    def test_scheme_definition(self, scheme_code: str = "PM-KISAN") -> bool:
        """Test getting specific scheme definition"""
        try:
            print(f"\n🧪 Testing scheme definition for {scheme_code}...")
            response = requests.get(f"{self.base_url}/api/schemes/{scheme_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    scheme = result.get('data')
                    print(f"✅ Scheme definition retrieved successfully")
                    print(f"   Name: {scheme.get('name')}")
                    print(f"   Ministry: {scheme.get('ministry')}")
                    print(f"   Status: {scheme.get('status')}")
                    print(f"   Data model sections: {len(scheme.get('data_model', []))}")
                    print(f"   Eligibility rules: {len(scheme.get('eligibility_rules', []))}")
                    print(f"   API endpoints: {len(scheme.get('api_endpoints', []))}")
                    return True
                else:
                    print(f"❌ Scheme definition failed: {result.get('message')}")
                    return False
            else:
                print(f"❌ Scheme definition failed: {response.status_code}")
                if response.status_code == 404:
                    print(f"   Scheme '{scheme_code}' not found")
                return False
        except Exception as e:
            print(f"❌ Scheme definition error: {e}")
            return False
    
    def test_data_model(self, scheme_code: str = "PM-KISAN") -> bool:
        """Test getting scheme data model"""
        try:
            print(f"\n🧪 Testing data model for {scheme_code}...")
            response = requests.get(f"{self.base_url}/api/schemes/{scheme_code}/data-model")
            
            if response.status_code == 200:
                data_model = response.json()
                print(f"✅ Data model retrieved successfully")
                print(f"   Scheme: {data_model.get('scheme_name')}")
                print(f"   Total fields: {data_model.get('total_fields', 0)}")
                print(f"   Required fields: {len(data_model.get('required_fields', []))}")
                print(f"   Data model sections: {len(data_model.get('data_model', []))}")
                
                # Show first few required fields
                required = data_model.get('required_fields', [])[:5]
                if required:
                    print(f"   Sample required fields: {', '.join(required)}")
                
                return True
            else:
                print(f"❌ Data model test failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Data model test error: {e}")
            return False
    
    def test_openapi_spec(self, scheme_code: str = "PM-KISAN") -> bool:
        """Test OpenAPI specification generation"""
        try:
            print(f"\n🧪 Testing OpenAPI spec for {scheme_code}...")
            response = requests.get(f"{self.base_url}/api/schemes/{scheme_code}/openapi")
            
            if response.status_code == 200:
                openapi_spec = response.json()
                print(f"✅ OpenAPI spec generated successfully")
                print(f"   OpenAPI version: {openapi_spec.get('openapi')}")
                print(f"   Title: {openapi_spec.get('info', {}).get('title')}")
                print(f"   Paths: {len(openapi_spec.get('paths', {}))}")
                print(f"   Schemas: {len(openapi_spec.get('components', {}).get('schemas', {}))}")
                print(f"   Tags: {len(openapi_spec.get('tags', []))}")
                return True
            else:
                print(f"❌ OpenAPI spec test failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ OpenAPI spec test error: {e}")
            return False
    
    def test_validation(self, scheme_code: str = "PM-KISAN") -> bool:
        """Test farmer data validation"""
        try:
            print(f"\n🧪 Testing validation for {scheme_code}...")
            
            # Test with valid data
            valid_data = {
                "farmer_id": "test123",
                "name": "Test Farmer",
                "age": 35,
                "gender": "male",
                "phone_number": "9876543210",
                "state": "Punjab",
                "district": "Ludhiana",
                "village": "Test Village",
                "sub_district_block": "Test Block",
                "land_size_acres": 2.5,
                "land_ownership": "owned",
                "date_of_land_ownership": "2018-01-01",
                "bank_account": True,
                "account_number": "123456789",
                "ifsc_code": "TEST0001234",
                "aadhaar_number": "123456789012",
                "aadhaar_linked": True,
                "category": "general"
            }
            
            response = requests.post(
                f"{self.base_url}/api/schemes/{scheme_code}/validate",
                json=valid_data
            )
            
            if response.status_code == 200:
                validation_result = response.json()
                print(f"✅ Validation completed")
                print(f"   Is valid: {validation_result.get('is_valid')}")
                print(f"   Errors: {len(validation_result.get('errors', []))}")
                print(f"   Warnings: {len(validation_result.get('warnings', []))}")
                
                if validation_result.get('errors'):
                    print(f"   Sample errors: {validation_result['errors'][:3]}")
                
                return True
            else:
                print(f"❌ Validation test failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Validation test error: {e}")
            return False
    
    def test_scheme_stats(self) -> bool:
        """Test scheme statistics"""
        try:
            print(f"\n🧪 Testing scheme statistics...")
            response = requests.get(f"{self.base_url}/api/schemes/stats")
            
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Statistics retrieved successfully")
                print(f"   Total schemes: {stats.get('total_schemes', 0)}")
                print(f"   API endpoints: {stats.get('api_endpoints_count', 0)}")
                print(f"   By status: {stats.get('by_status', {})}")
                print(f"   By ministry: {stats.get('by_ministry', {})}")
                print(f"   By category: {stats.get('by_category', {})}")
                return True
            else:
                print(f"❌ Statistics test failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Statistics test error: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all test cases"""
        print("🚀 Starting EFR Database Scheme API Tests...")
        print(f"Base URL: {self.base_url}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        tests = [
            ("Connection", self.test_connection),
            ("Scheme Registry", self.test_scheme_registry),
            ("List Schemes", self.test_list_schemes),
            ("Scheme Definition", self.test_scheme_definition),
            ("Data Model", self.test_data_model),
            ("OpenAPI Spec", self.test_openapi_spec),
            ("Data Validation", self.test_validation),
            ("Scheme Statistics", self.test_scheme_stats)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                self.test_results[test_name] = result
                if result:
                    passed += 1
            except Exception as e:
                print(f"❌ {test_name} test crashed: {e}")
                self.test_results[test_name] = False
        
        print(f"\n📊 Test Results: {passed}/{total} tests passed")
        print("="*50)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
        
        return passed == total

def main():
    """Main test function"""
    base_url = "http://localhost:8001"
    
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    tester = SchemeAPITester(base_url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 