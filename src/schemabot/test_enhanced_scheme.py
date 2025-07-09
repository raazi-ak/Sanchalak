#!/usr/bin/env python3
"""
Test script for Enhanced PM-KISAN Scheme with Canonical Enhanced Model
Demonstrates the integration of the canonical enhanced model into schemabot
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.scheme.enhanced_parser import EnhancedSchemeParser, load_enhanced_scheme, validate_extracted_data, generate_extraction_prompt
from core.scheme.canonical_models import CanonicalScheme

def test_enhanced_scheme_loading():
    """Test loading the enhanced PM-KISAN scheme"""
    print("=== Testing Enhanced Scheme Loading ===")
    
    try:
        # Load the enhanced scheme
        scheme_file = "schemas/pm_kisan_enhanced.yaml"
        scheme = load_enhanced_scheme(scheme_file)
        
        print(f"✅ Successfully loaded scheme: {scheme.name}")
        print(f"   Code: {scheme.code}")
        print(f"   Ministry: {scheme.ministry}")
        print(f"   Data model sections: {list(scheme.data_model.keys())}")
        
        # Show some data model details
        print("\n📋 Data Model Overview:")
        for section_name, section in scheme.data_model.items():
            print(f"   {section_name}: {len(section)} fields")
            for field_name, field_def in list(section.items())[:3]:  # Show first 3 fields
                print(f"     - {field_name}: {field_def.type} ({'required' if field_def.required else 'optional'})")
            if len(section) > 3:
                print(f"     ... and {len(section) - 3} more fields")
        
        return scheme
        
    except Exception as e:
        print(f"❌ Error loading scheme: {e}")
        return None

def test_data_validation():
    """Test data validation against the enhanced scheme"""
    print("\n=== Testing Data Validation ===")
    
    try:
        scheme = load_enhanced_scheme("schemas/pm_kisan_enhanced.yaml")
        
        # Test valid data
        valid_data = {
            "farmer_id": "FARMER001",
            "name": "John Doe",
            "age": 45,
            "gender": "male",
            "phone_number": "9876543210",
            "state": "Manipur",
            "district": "Imphal East",
            "sub_district_block": "Porompat",
            "village": "Kongba",
            "land_size_acres": 3.5,
            "land_ownership": "owned",
            "date_of_land_ownership": "2018-06-15",
            "bank_account": True,
            "account_number": "1234567890",
            "ifsc_code": "SBIN0001234",
            "aadhaar_number": "123456789012",
            "aadhaar_linked": True,
            "category": "general",
            "region_special": "manipur",
            "has_special_certificate": True,
            "certificate_type": "village_authority_certificate"
        }
        
        result = validate_extracted_data(valid_data, scheme)
        print(f"✅ Valid data validation: {'PASS' if result['is_valid'] else 'FAIL'}")
        if result['errors']:
            print(f"   Errors: {result['errors']}")
        
        # Test invalid data
        invalid_data = {
            "farmer_id": "FARMER002",
            "name": "",  # Empty name
            "age": 15,   # Under 18
            "gender": "invalid",  # Invalid gender
            "phone_number": "123",  # Invalid phone
            "aadhaar_number": "123",  # Invalid Aadhaar
        }
        
        result = validate_extracted_data(invalid_data, scheme)
        print(f"✅ Invalid data validation: {'PASS' if not result['is_valid'] else 'FAIL'}")
        if result['errors']:
            print(f"   Expected errors: {result['errors']}")
        
    except Exception as e:
        print(f"❌ Error in validation test: {e}")

def test_extraction_prompt_generation():
    """Test LLM extraction prompt generation"""
    print("\n=== Testing Extraction Prompt Generation ===")
    
    try:
        scheme = load_enhanced_scheme("schemas/pm_kisan_enhanced.yaml")
        
        sample_transcript = """
        Hello, I am Ram Singh from Manipur. I am 45 years old and I have 3.5 acres of land 
        which I own since 2018. I have a bank account and my Aadhaar is linked. I am from 
        Imphal East district, Porompat block, Kongba village. I have a certificate from 
        the village authority for land cultivation.
        """
        
        prompt = generate_extraction_prompt(scheme, sample_transcript)
        print("✅ Generated extraction prompt:")
        print(f"   Length: {len(prompt)} characters")
        print(f"   Contains special region detection: {'Yes' if 'SPECIAL REGION DETECTION' in prompt else 'No'}")
        print(f"   Contains conditional fields: {'Yes' if 'CONDITIONAL FIELDS' in prompt else 'No'}")
        
        # Show a snippet of the prompt
        print(f"   Prompt snippet: {prompt[:200]}...")
        
    except Exception as e:
        print(f"❌ Error in prompt generation test: {e}")

def test_legacy_conversion():
    """Test conversion to legacy format for backward compatibility"""
    print("\n=== Testing Legacy Format Conversion ===")
    
    try:
        scheme = load_enhanced_scheme("schemas/pm_kisan_enhanced.yaml")
        parser = EnhancedSchemeParser()
        
        legacy_scheme = parser.convert_to_legacy_format(scheme)
        
        print(f"✅ Successfully converted to legacy format")
        print(f"   Legacy scheme ID: {legacy_scheme.id}")
        print(f"   Legacy scheme name: {legacy_scheme.name}")
        print(f"   Number of eligibility rules: {len(legacy_scheme.eligibility.rules)}")
        print(f"   Number of benefits: {len(legacy_scheme.benefits)}")
        
    except Exception as e:
        print(f"❌ Error in legacy conversion test: {e}")

def test_special_region_handling():
    """Test special region detection and handling"""
    print("\n=== Testing Special Region Handling ===")
    
    try:
        scheme = load_enhanced_scheme("schemas/pm_kisan_enhanced.yaml")
        
        # Test Manipur special region
        manipur_data = {
            "state": "Manipur",
            "region_special": "manipur",
            "has_special_certificate": True,
            "certificate_type": "village_authority_certificate",
            "certificate_details": {
                "issued_by": "Village Chief",
                "issue_date": "2024-01-15",
                "authenticated_by": "Sub-divisional Officer"
            }
        }
        
        result = validate_extracted_data(manipur_data, scheme)
        print(f"✅ Manipur special region validation: {'PASS' if result['is_valid'] else 'FAIL'}")
        
        # Test Jharkhand special region
        jharkhand_data = {
            "state": "Jharkhand",
            "region_special": "jharkhand",
            "has_special_certificate": True,
            "certificate_type": "vanshavali_certificate",
            "certificate_details": {
                "issued_by": "Village Revenue Officials",
                "issue_date": "2024-01-15",
                "authenticated_by": "District Revenue Authority",
                "lineage_chart_submitted": True,
                "gram_sabha_verified": True
            }
        }
        
        result = validate_extracted_data(jharkhand_data, scheme)
        print(f"✅ Jharkhand special region validation: {'PASS' if result['is_valid'] else 'FAIL'}")
        
    except Exception as e:
        print(f"❌ Error in special region test: {e}")

def main():
    """Run all tests"""
    print("🚀 Testing Enhanced PM-KISAN Scheme with Canonical Enhanced Model")
    print("=" * 70)
    
    # Run all tests
    test_enhanced_scheme_loading()
    test_data_validation()
    test_extraction_prompt_generation()
    test_legacy_conversion()
    test_special_region_handling()
    
    print("\n" + "=" * 70)
    print("✅ All tests completed!")

if __name__ == "__main__":
    main() 