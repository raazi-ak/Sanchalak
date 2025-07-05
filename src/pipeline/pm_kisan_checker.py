#!/usr/bin/env python3
"""
Simple PM-KISAN Eligibility Checker
Takes farmer data and checks eligibility using Prolog
"""

import sys
import os
import json
import requests
from typing import Dict, Any, List, Tuple
from pyswip import Prolog

# Get the root directory of the project
def get_project_root():
    """Get the absolute path to the project root directory."""
    current_file = os.path.abspath(__file__)
    # Navigate up from src/pipeline to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    return project_root

# Set up absolute paths
PROJECT_ROOT = get_project_root()
PROLOG_FILE_PATH = os.path.join(PROJECT_ROOT, "src", "schemes", "outputs", "pm-kisan", "REFERENCE_prolog_system.pl")

REQUIRED_FIELDS = [
    'name', 'age', 'gender', 'phone_number', 'state', 'district', 'village',
    'land_size_acres', 'land_ownership', 'date_of_land_ownership', 'land_owner',
    'annual_income', 'bank_account', 'aadhaar_linked', 'category', 'region',
    'family_members',
    # Exclusion fields
    'is_constitutional_post_holder', 'is_political_office_holder', 'is_government_employee',
    'government_post', 'monthly_pension', 'is_income_tax_payer', 'is_professional', 'is_nri', 'is_pensioner'
]

class PMKisanChecker:
    def __init__(self, prolog_file: str = None):
        """Initialize the PM-KISAN eligibility checker."""
        if prolog_file is None:
            prolog_file = PROLOG_FILE_PATH
        
        self.prolog_file = prolog_file
        self.prolog = Prolog()
        self.load_prolog()
    
    def load_prolog(self):
        """Load the Prolog system."""
        try:
            self.prolog.consult(self.prolog_file)
        except Exception as e:
            print(f"❌ Failed to load Prolog: {e}")
            raise
    
    def get_farmer_from_efr(self, farmer_id: str) -> Dict[str, Any]:
        """Get farmer data from EFR database."""
        try:
            response = requests.get(f"http://localhost:8000/farmer/{farmer_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Failed to get farmer {farmer_id}: {e}")
            return None
    
    def convert_to_prolog_facts(self, farmer_data: Dict[str, Any]) -> List[str]:
        """Convert farmer data to Prolog facts."""
        facts = []
        farmer_name = farmer_data.get('name', 'farmer')
        quoted_name = f"'{farmer_name}'"
        
        # Basic facts
        facts.append(f"person({quoted_name})")
        
        # Map EFR fields to Prolog predicates
        field_mappings = {
            'name': 'name',
            'age': 'age',
            'gender': 'gender',
            'phone_number': 'phone_number',
            'state': 'state',
            'district': 'district',
            'village': 'village',
            'sub_district_block': 'sub_district_block',
            'land_size_acres': 'land_size_acres',
            'land_ownership': 'land_ownership',
            'date_of_land_ownership': 'date_of_land_ownership',
            'land_owner': 'land_owner',
            'annual_income': 'annual_income',
            'bank_account': 'bank_account',
            'has_kisan_credit_card': 'has_kisan_credit_card',
            'aadhaar_linked': 'aadhaar_linked',
            'category': 'category',
            'family_definition': 'family_definition',
            'region': 'region',
            'farmer_id': 'farmer_id',
            'account_number': 'account_number',
            'ifsc_code': 'ifsc_code',
            'aadhaar_number': 'aadhaar_number',
            'profession': 'profession',
            'government_post': 'government_post',
            'is_government_employee': 'is_government_employee',
            'is_pensioner': 'is_pensioner',
            'monthly_pension': 'monthly_pension',
            'is_constitutional_post_holder': 'is_constitutional_post_holder',
            'is_political_office_holder': 'is_political_office_holder',
            'is_income_tax_payer': 'is_income_tax_payer',
            'is_professional': 'is_professional',
            'is_nri': 'is_nri',
            'special_provisions': 'special_provisions'
        }
        
        for efr_field, prolog_predicate in field_mappings.items():
            value = farmer_data.get(efr_field)
            if value is not None:
                if efr_field == 'special_provisions':
                    # Handle special_provisions dictionary specially
                    if isinstance(value, dict) and 'pm_kisan' in value:
                        pm_kisan_data = value['pm_kisan']
                        # Add individual special provision facts
                        region_special = pm_kisan_data.get('region_special', 'none')
                        has_cert = pm_kisan_data.get('has_special_certificate', False)
                        cert_type = pm_kisan_data.get('certificate_type', 'none')
                        cert_details = pm_kisan_data.get('certificate_details', 'none')
                        
                        facts.append(f"region_special({quoted_name}, '{region_special}')")
                        facts.append(f"has_special_certificate({quoted_name}, {str(has_cert).lower()})")
                        facts.append(f"certificate_type({quoted_name}, '{cert_type}')")
                        facts.append(f"certificate_details({quoted_name}, '{cert_details}')")
                elif isinstance(value, bool):
                    fact = f"{prolog_predicate}({quoted_name}, {str(value).lower()})"
                    facts.append(fact)
                elif isinstance(value, (int, float)):
                    fact = f"{prolog_predicate}({quoted_name}, {value})"
                    facts.append(fact)
                else:
                    fact = f"{prolog_predicate}({quoted_name}, '{value}')"
                    facts.append(fact)
        
        # Handle family members (strict - age must be present and integer)
        # First, add the main person as 'self'
        main_person_age = farmer_data.get('age')
        if main_person_age is not None:
            try:
                age = int(main_person_age)
                fact = f"family_member({quoted_name}, 'self', {age})"
                facts.append(fact)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid age for main person: {main_person_age}")
        
        # Then add other family members
        family_members = farmer_data.get('family_members')
        if family_members is None:
            family_members = []
        for member in family_members:
            relation = member.get('relation', 'unknown')
            if 'age' not in member:
                raise ValueError(f"Missing age for family member: {member}")
            try:
                age = int(member['age'])
            except (TypeError, ValueError):
                raise ValueError(f"Invalid age for family member: {member}")
            fact = f"family_member({quoted_name}, '{relation}', {age})"
            facts.append(fact)
        
        # Add missing exclusion predicates with defaults
        exclusion_fields = [
            'is_constitutional_post_holder',
            'is_political_office_holder',
            'monthly_pension',
            'is_income_tax_payer',
            'is_professional',
            'is_nri'
        ]
        
        for field in exclusion_fields:
            if field not in farmer_data:
                if field == 'monthly_pension':
                    fact = f"{field}({quoted_name}, 0)"
                else:
                    fact = f"{field}({quoted_name}, false)"
                facts.append(fact)
        
        # Add missing government_post if not present
        if 'government_post' not in farmer_data:
            fact = f"government_post({quoted_name}, 'none')"
            facts.append(fact)
        
        return facts
    
    def add_facts_to_prolog(self, facts: List[str]):
        """Add facts to Prolog system."""
        for fact in facts:
            try:
                self.prolog.assertz(fact)
            except Exception as e:
                print(f"⚠️ Could not add fact '{fact}': {e}")
    
    def check_eligibility(self, farmer_id: str, farmer_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check eligibility for a farmer and provide a detailed explanation.
        """
        print(f"\n{'='*60}")
        print(f"🔍 DETAILED ELIGIBILITY ANALYSIS FOR FARMER: {farmer_id}")
        print(f"{'='*60}")
        
        # 1. Check for missing required fields
        print(f"\n📋 STEP 1: Checking Required Fields")
        print(f"{'-'*40}")
        missing = [f for f in REQUIRED_FIELDS if f not in farmer_data]
        if missing:
            print(f"❌ CRITICAL ERROR: Missing required EFR fields:")
            for field in missing:
                print(f"   • {field}")
            print(f"\n💡 SOLUTION: Please ensure all required fields are present in EFR data.")
            print(f"   Required fields: {REQUIRED_FIELDS}")
            return False, f"Missing required fields: {missing}"
        else:
            print(f"✅ All required fields present")
        
        # 2. Print all field values for debugging
        print(f"\n📊 STEP 2: Current Field Values")
        print(f"{'-'*40}")
        for field in sorted(farmer_data.keys()):
            value = farmer_data[field]
            value_type = type(value).__name__
            print(f"   {field:25} = {value} ({value_type})")
        
        # 3. Generate and validate Prolog facts
        print(f"\n🔧 STEP 3: Generating Prolog Facts")
        print(f"{'-'*40}")
        facts = self.convert_to_prolog_facts(farmer_data)
        print(f"✅ Generated {len(facts)} Prolog facts")
        
        # Print all facts for audit
        print(f"\n📝 STEP 4: Prolog Facts (for debugging)")
        print(f"{'-'*40}")
        for i, fact in enumerate(facts, 1):
            print(f"   {i:2d}. {fact}.")
        
        # 5. Add facts to Prolog and run queries
        print(f"\n🤖 STEP 5: Running Prolog Queries")
        print(f"{'-'*40}")
        
        try:
            # Clear any existing facts for this farmer
            farmer_name = farmer_data.get('name', farmer_id)
            quoted_name = f"'{farmer_name}'"
            
            # Clear all existing facts for this person
            try:
                self.prolog.retractall(f"person({quoted_name})")
                self.prolog.retractall(f"family_member({quoted_name}, _, _)")
                self.prolog.retractall(f"land_owner({quoted_name}, _)")
                self.prolog.retractall(f"aadhaar_linked({quoted_name}, _)")
                self.prolog.retractall(f"bank_account({quoted_name}, _)")
                self.prolog.retractall(f"category({quoted_name}, _)")
                self.prolog.retractall(f"region({quoted_name}, _)")
                self.prolog.retractall(f"date_of_land_ownership({quoted_name}, _)")
            except Exception as e:
                print(f"⚠️  Warning: Could not clear existing facts: {e}")
            
            # Add all facts
            for fact in facts:
                try:
                    self.prolog.assertz(fact)
                except Exception as e:
                    print(f"⚠️  Warning: Could not assert fact '{fact}': {e}")
            
            # Test basic queries
            print(f"🔍 Testing basic Prolog queries...")
            
            # Check if person exists
            person_exists = bool(list(self.prolog.query(f"person({quoted_name})")))
            print(f"   • person({quoted_name}): {'✅ YES' if person_exists else '❌ NO'}")
            
            # Check if land_owner exists and value
            land_owner_results = list(self.prolog.query(f"land_owner({quoted_name}, Value)"))
            if land_owner_results:
                land_owner_value = land_owner_results[0]['Value']
                print(f"   • land_owner({quoted_name}, {land_owner_value}): ✅ FOUND")
            else:
                print(f"   • land_owner({quoted_name}, _): ❌ NOT FOUND")
            
            # Check if aadhaar_linked exists and value
            aadhaar_results = list(self.prolog.query(f"aadhaar_linked({quoted_name}, Value)"))
            if aadhaar_results:
                aadhaar_value = aadhaar_results[0]['Value']
                print(f"   • aadhaar_linked({quoted_name}, {aadhaar_value}): ✅ FOUND")
            else:
                print(f"   • aadhaar_linked({quoted_name}, _): ❌ NOT FOUND")
            
            # 6. Run eligibility check
            print(f"\n🎯 STEP 6: Eligibility Determination")
            print(f"{'-'*40}")
            
            eligible = bool(list(self.prolog.query(f"eligible({quoted_name})")))
            print(f"Final eligibility result: {'✅ ELIGIBLE' if eligible else '❌ NOT ELIGIBLE'}")
            
            # 7. Get comprehensive diagnostic explanation
            print(f"\n📖 STEP 7: Detailed Reasoning Analysis")
            print(f"{'-'*40}")
            
            # Check each exclusion rule individually
            print(f"🔍 EXCLUSION ANALYSIS:")
            exclusion_rules = [
                ('institutional_land_holder', 'Institutional Land Holder'),
                ('constitutional_post_holder', 'Constitutional Post Holder'),
                ('political_office_holder', 'Political Office Holder'),
                ('government_employee', 'Government Employee'),
                ('high_pension_pensioner', 'High Pension Pensioner'),
                ('income_tax_payer', 'Income Tax Payer'),
                ('professional', 'Professional'),
                ('nri', 'NRI')
            ]
            
            active_exclusions = []
            for exclusion_code, exclusion_name in exclusion_rules:
                exclusion_results = list(self.prolog.query(f"exclusion_applies({quoted_name}, {exclusion_code})"))
                if exclusion_results:
                    active_exclusions.append(exclusion_name)
                    print(f"   ❌ {exclusion_name}: EXCLUDED")
                    
                    # Get specific details for government employee exclusion
                    if exclusion_code == 'government_employee':
                        gov_emp_results = list(self.prolog.query(f"is_government_employee({quoted_name}, Value)"))
                        gov_post_results = list(self.prolog.query(f"government_post({quoted_name}, Post)"))
                        if gov_emp_results and gov_post_results:
                            is_emp = gov_emp_results[0]['Value']
                            post = gov_post_results[0]['Post']
                            print(f"      → is_government_employee: {is_emp}")
                            print(f"      → government_post: {post}")
                            print(f"      → Rule: All government employees excluded except Group D/MTS")
                    
                    # Get specific details for institutional land holder
                    elif exclusion_code == 'institutional_land_holder':
                        land_own_results = list(self.prolog.query(f"land_ownership({quoted_name}, Value)"))
                        if land_own_results:
                            land_type = land_own_results[0]['Value']
                            print(f"      → land_ownership: {land_type}")
                            print(f"      → Rule: Institutional land holders are excluded")
                    
                    # Get specific details for high pension pensioner
                    elif exclusion_code == 'high_pension_pensioner':
                        pension_results = list(self.prolog.query(f"monthly_pension({quoted_name}, Amount)"))
                        gov_post_results = list(self.prolog.query(f"government_post({quoted_name}, Post)"))
                        if pension_results:
                            pension_amount = pension_results[0]['Amount']
                            print(f"      → monthly_pension: Rs. {pension_amount}")
                            print(f"      → Rule: Pensioners with pension >= Rs. 10,000 excluded (except Group D/MTS)")
                            if gov_post_results:
                                gov_post = gov_post_results[0]['Post']
                                print(f"      → government_post: {gov_post}")
                                if gov_post in ['Group D', 'MTS', 'Multi Tasking Staff']:
                                    print(f"      → ⚠️  WARNING: Should be exempt as Group D/MTS employee!")
                else:
                    print(f"   ✅ {exclusion_name}: NOT EXCLUDED")
            
            # Check family structure
            print(f"\n👨‍👩‍👧‍👦 FAMILY STRUCTURE ANALYSIS:")
            family_results = list(self.prolog.query(f"family_eligible({quoted_name})"))
            if family_results:
                print(f"   ✅ Family structure: ELIGIBLE")
                # Show family members
                family_members = list(self.prolog.query(f"family_member({quoted_name}, Relation, Age)"))
                for member in family_members:
                    relation = member['Relation']
                    age = member['Age']
                    print(f"      → {relation}: {age} years old")
            else:
                print(f"   ❌ Family structure: NOT ELIGIBLE")
                print(f"      → Rule: Must have husband, wife, and minor children (< 18)")
                # Show what family members exist
                family_members = list(self.prolog.query(f"family_member({quoted_name}, Relation, Age)"))
                for member in family_members:
                    relation = member['Relation']
                    age = member['Age']
                    print(f"      → {relation}: {age} years old")
            
            # Check key requirements
            print(f"\n📋 KEY REQUIREMENTS ANALYSIS:")
            key_requirements = [
                ('land_owner', 'Land Owner'),
                ('aadhaar_linked', 'Aadhaar Linked'),
                ('bank_account', 'Bank Account'),
                ('date_of_land_ownership', 'Land Ownership Date')
            ]
            
            for req_pred, req_name in key_requirements:
                req_results = list(self.prolog.query(f"{req_pred}({quoted_name}, Value)"))
                if req_results:
                    value = req_results[0]['Value']
                    if isinstance(value, bool):
                        status = "✅ PASS" if value else "❌ FAIL"
                    else:
                        status = "✅ PASS" if value else "❌ FAIL"
                    print(f"   {status} {req_name}: {value}")
                else:
                    print(f"   ❌ FAIL {req_name}: NOT FOUND")
            
            # Final reasoning
            print(f"\n🎯 FINAL REASONING:")
            if active_exclusions:
                print(f"   ❌ NOT ELIGIBLE due to exclusions:")
                for exclusion in active_exclusions:
                    print(f"      • {exclusion}")
            else:
                print(f"   ✅ NO EXCLUSIONS APPLY")
                
            if not family_results:
                print(f"   ❌ NOT ELIGIBLE due to family structure")
            else:
                print(f"   ✅ FAMILY STRUCTURE OK")
            
            return eligible, "Detailed analysis completed above"
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: Prolog execution failed")
            print(f"   Error: {e}")
            print(f"   This indicates a serious issue with the Prolog system or data format")
            return False, f"Prolog execution error: {e}"
        
        finally:
            print(f"\n{'='*60}")
            print(f"🏁 ELIGIBILITY ANALYSIS COMPLETE")
            print(f"{'='*60}")
    
    def get_explanation(self, farmer_name: str) -> Dict[str, Any]:
        """Get detailed eligibility explanation."""
        try:
            result = list(self.prolog.query(f"explain_eligibility({farmer_name})"))
            return {
                "person": farmer_name,
                "explanation": "Eligibility check completed",
                "eligible": self.check_eligibility(farmer_name)
            }
        except Exception as e:
            return {
                "person": farmer_name,
                "error": str(e),
                "eligible": False
            }
    
    def check_farmer(self, farmer_id: str) -> Dict[str, Any]:
        """Complete eligibility check for a farmer."""
        print(f"🔍 Checking eligibility for farmer: {farmer_id}")
        
        # Get farmer data
        farmer_data = self.get_farmer_from_efr(farmer_id)
        if not farmer_data:
            return {"error": f"Farmer {farmer_id} not found"}
        
        farmer_name = farmer_data.get('name', farmer_id)
        print(f"✅ Found farmer: {farmer_name}")
        
        # Convert to Prolog facts
        facts = self.convert_to_prolog_facts(farmer_data)
        print(f"📝 Generated {len(facts)} Prolog facts")
        
        # Add facts to Prolog
        self.add_facts_to_prolog(facts)
        
        # Check eligibility
        is_eligible, explanation = self.check_eligibility(farmer_id, farmer_data)
        
        return {
            "farmer_id": farmer_id,
            "farmer_name": farmer_name,
            "eligible": is_eligible,
            "explanation": explanation,
            "facts_generated": len(facts)
        }

def main():
    """Main function to test the checker."""
    if len(sys.argv) < 2:
        print("Usage: python pm_kisan_checker.py <farmer_id>")
        sys.exit(1)
    
    farmer_id = sys.argv[1]
    checker = PMKisanChecker()
    
    result = checker.check_farmer(farmer_id)
    
    print(f"\n📊 Eligibility Result:")
    print(f"Farmer: {result.get('farmer_name', 'Unknown')}")
    print(f"Eligible: {'✅ YES' if result.get('eligible') else '❌ NO'}")
    print(f"Facts: {result.get('facts_generated', 0)}")
    
    if 'error' in result:
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    main() 