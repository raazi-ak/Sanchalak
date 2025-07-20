#!/usr/bin/env python3
"""
Test script for the eligibility endpoint
"""

import requests
import json

def test_eligibility_endpoint():
    """Test the eligibility endpoint with sample data"""
    
    # Sample farmer data
    farmer_data = {
        "name": "Ramesh Kumar",
        "age": 45,
        "gender": "male",
        "phone_number": "9876543210",
        "state": "Punjab",
        "district": "Amritsar",
        "village": "Test Village",
        "land_size_acres": 2.5,
        "land_ownership": "owned",
        "date_of_land_ownership": "2010-01-01",
        "land_owner": "self",
        "annual_income": 80000,
        "bank_account": "1234567890",
        "aadhaar_linked": True,
        "category": "small_farmer",
        "region": "general",
        "family_members": [
            {"relation": "spouse", "age": 40, "gender": "female"},
            {"relation": "son", "age": 20, "gender": "male"}
        ],
        # Exclusion criteria
        "is_constitutional_post_holder": False,
        "is_political_office_holder": False,
        "is_government_employee": False,
        "government_post": "none",
        "monthly_pension": 0,
        "is_income_tax_payer": False,
        "is_professional": False,
        "is_nri": False,
        "is_pensioner": False
    }
    
    # Test data
    test_request = {
        "scheme_id": "pm-kisan",
        "farmer_data": farmer_data,
        "farmer_id": "TEST001"
    }
    
    try:
        # Test the eligibility endpoint
        print("🔍 Testing eligibility endpoint...")
        response = requests.post(
            "http://localhost:8002/eligibility/check",
            json=test_request,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Eligibility check successful!")
            print(f"📋 Scheme ID: {result.get('scheme_id')}")
            print(f"👨‍🌾 Farmer ID: {result.get('farmer_id')}")
            print(f"✅ Eligible: {result.get('is_eligible')}")
            print(f"📝 Explanation: {result.get('explanation')}")
            print(f"🎯 Confidence: {result.get('confidence_score')}")
            print(f"📊 Details: {json.dumps(result.get('details', {}), indent=2)}")
        else:
            print(f"❌ Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to scheme server. Make sure it's running on port 8002.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_efr_farmer_fetch():
    """Test fetching a farmer from EFR database"""
    
    try:
        print("\n🔍 Testing EFR farmer fetch...")
        response = requests.get("http://localhost:8001/farmer/TEST001")
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            farmer = response.json()
            print("✅ Farmer fetch successful!")
            print(f"👨‍🌾 Name: {farmer.get('name')}")
            print(f"📱 Phone: {farmer.get('phone_number')}")
            print(f"🏠 State: {farmer.get('state')}")
        else:
            print(f"❌ Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to EFR server. Make sure it's running on port 8001.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 Testing Eligibility Endpoint")
    print("=" * 50)
    
    # Test EFR farmer fetch first
    test_efr_farmer_fetch()
    
    # Test eligibility endpoint
    test_eligibility_endpoint() 