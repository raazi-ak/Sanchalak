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

# Get the scheme directory
def get_scheme_dir():
    """Get the absolute path to the PM-KISAN scheme directory."""
    current_file = os.path.abspath(__file__)
    scheme_dir = os.path.dirname(current_file)
    return scheme_dir

# Set up absolute paths
SCHEME_DIR = get_scheme_dir()
PROLOG_FILE_PATH = os.path.join(SCHEME_DIR, "REFERENCE_prolog_system.pl")

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
            headers = {"x-api-key": "thisisourhardworkpleasedontcopy"}
            response = requests.get(f"http://localhost:8001/farmer/{farmer_id}", headers=headers)
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
        print(f"\n🤖 STEP 5: Running Prolog Queries (Verbose Mode)")
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
            
            # --- VERBOSE REQUIREMENT CHECKS ---
            print(f"\n🔍 VERBOSE REQUIREMENT CHECKS:")
            for req in [
                'name', 'age', 'gender', 'phone_number', 'state', 'district', 'sub_district_block', 'village',
                'land_size_acres', 'land_owner', 'date_of_land_ownership', 'bank_account', 'account_number',
                'ifsc_code', 'aadhaar_number', 'aadhaar_linked', 'category', 'region']:
                try:
                    print(f"[DEBUG] Querying requirement_met({quoted_name}, {req})...")
                    result = bool(list(self.prolog.query(f"requirement_met({quoted_name}, {req})")))
                    print(f"[DEBUG] Result: {result}")
                    print(f"   • Requirement '{req}': {'✅ PASS' if result else '❌ FAIL'}")
                except Exception as e:
                    print(f"   • Requirement '{req}': ⚠️ ERROR: {e}")
            
            # --- VERBOSE CONDITIONAL REQUIREMENT CHECKS ---
            print(f"\n🔍 VERBOSE CONDITIONAL REQUIREMENT CHECKS:")
            conditional_requirements = [
                ('government_employee_post', 'Government Employee Post'),
                ('professional_profession', 'Professional Profession'), 
                ('pensioner_pension', 'Pensioner Pension'),
                ('special_region_certificate', 'Special Region Certificate')
            ]
            
            for creq_code, creq_name in conditional_requirements:
                try:
                    print(f"[DEBUG] Querying check_conditional_requirement({quoted_name}, {creq_code})...")
                    result = bool(list(self.prolog.query(f"check_conditional_requirement({quoted_name}, {creq_code})")))
                    print(f"[DEBUG] Result: {result}")
                    
                    if result:
                        print(f"   ✅ Conditional '{creq_name}': PASS")
                        # Get detailed reasoning for why it passed
                        if creq_code == 'special_region_certificate':
                            # Get special provision details
                            region_results = list(self.prolog.query(f"region_special({quoted_name}, Region)"))
                            cert_results = list(self.prolog.query(f"has_special_certificate({quoted_name}, HasCert)"))
                            cert_type_results = list(self.prolog.query(f"certificate_type({quoted_name}, CertType)"))
                            
                            if region_results and cert_results and cert_type_results:
                                region = region_results[0]['Region']
                                has_cert = cert_results[0]['HasCert']
                                cert_type = cert_type_results[0]['CertType']
                                print(f"      → Region: {region}")
                                print(f"      → Has Certificate: {has_cert}")
                                print(f"      → Certificate Type: {cert_type}")
                                print(f"      → Rule: Special region certificate required and validated")
                        
                        elif creq_code == 'government_employee_post':
                            gov_emp_results = list(self.prolog.query(f"is_government_employee({quoted_name}, IsEmp)"))
                            gov_post_results = list(self.prolog.query(f"government_post({quoted_name}, Post)"))
                            if gov_emp_results and gov_post_results:
                                is_emp = gov_emp_results[0]['IsEmp']
                                post = gov_post_results[0]['Post']
                                print(f"      → Is Government Employee: {is_emp}")
                                print(f"      → Government Post: {post}")
                                print(f"      → Rule: Government employees must be Group D/MTS to be eligible")
                        
                        elif creq_code == 'professional_profession':
                            prof_results = list(self.prolog.query(f"is_professional({quoted_name}, IsProf)"))
                            profession_results = list(self.prolog.query(f"profession({quoted_name}, Profession)"))
                            if prof_results and profession_results:
                                is_prof = prof_results[0]['IsProf']
                                profession = profession_results[0]['Profession']
                                print(f"      → Is Professional: {is_prof}")
                                print(f"      → Profession: {profession}")
                                print(f"      → Rule: Professionals are excluded unless special conditions apply")
                        
                        elif creq_code == 'pensioner_pension':
                            pension_results = list(self.prolog.query(f"is_pensioner({quoted_name}, IsPensioner)"))
                            pension_amount_results = list(self.prolog.query(f"monthly_pension({quoted_name}, Amount)"))
                            if pension_results and pension_amount_results:
                                is_pensioner = pension_results[0]['IsPensioner']
                                amount = pension_amount_results[0]['Amount']
                                print(f"      → Is Pensioner: {is_pensioner}")
                                print(f"      → Monthly Pension: Rs. {amount}")
                                print(f"      → Rule: Pensioners with pension >= Rs. 10,000 are excluded")
                    else:
                        print(f"   ❌ Conditional '{creq_name}': FAIL")
                        # Get detailed reasoning for why it failed
                        if creq_code == 'special_region_certificate':
                            print(f"      → Rule: No special region certificate required or validation failed")
                        elif creq_code == 'government_employee_post':
                            print(f"      → Rule: Not a government employee or post not eligible")
                        elif creq_code == 'professional_profession':
                            print(f"      → Rule: Not a professional or profession not applicable")
                        elif creq_code == 'pensioner_pension':
                            print(f"      → Rule: Not a pensioner or pension amount not applicable")
                            
                except Exception as e:
                    print(f"   • Conditional '{creq_name}': ⚠️ ERROR: {e}")
            
            # --- VERBOSE EXCLUSION CHECKS ---
            print(f"\n🔍 VERBOSE EXCLUSION CHECKS:")
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
            for exclusion_code, exclusion_name in exclusion_rules:
                try:
                    print(f"[DEBUG] Querying exclusion_applies({quoted_name}, {exclusion_code})...")
                    result = bool(list(self.prolog.query(f"exclusion_applies({quoted_name}, {exclusion_code})")))
                    print(f"[DEBUG] Result: {result}")
                    print(f"   • Exclusion '{exclusion_name}': {'❌ EXCLUDED' if result else '✅ NOT EXCLUDED'}")
                except Exception as e:
                    print(f"   • Exclusion '{exclusion_name}': ⚠️ ERROR: {e}")
            
            # 6. Run eligibility check
            print(f"\n🎯 STEP 6: Eligibility Determination")
            print(f"{'-'*40}")
            print(f"[DEBUG] Querying eligible({quoted_name})...")
            eligible = bool(list(self.prolog.query(f"eligible({quoted_name})")))
            print(f"[DEBUG] Result: {eligible}")
            print(f"Final eligibility result: {'✅ ELIGIBLE' if eligible else '❌ NOT ELIGIBLE'}")
            
            # 7. Get comprehensive diagnostic explanation
            print(f"\n📖 STEP 7: Detailed Reasoning Analysis")
            print(f"{'-'*40}")
            
            # Check each exclusion rule individually
            print(f"🔍 EXCLUSION ANALYSIS:")
            active_exclusions = []
            for exclusion_code, exclusion_name in exclusion_rules:
                print(f"[DEBUG] Querying exclusion_applies({quoted_name}, {exclusion_code}) for analysis...")
                exclusion_results = list(self.prolog.query(f"exclusion_applies({quoted_name}, {exclusion_code})"))
                print(f"[DEBUG] Result: {exclusion_results}")
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
            
            # Check family structure with detailed reasoning
            print(f"\n👨‍👩‍👧‍👦 FAMILY STRUCTURE ANALYSIS:")
            print(f"[DEBUG] Querying family_eligible({quoted_name})...")
            family_results = list(self.prolog.query(f"family_eligible({quoted_name})"))
            print(f"[DEBUG] Result: {family_results}")
            family_members = list(self.prolog.query(f"family_member({quoted_name}, Relation, Age)"))
            print(f"[DEBUG] family_member results: {family_members}")
            
            if family_results:
                print(f"   ✅ Family structure: ELIGIBLE")
                print(f"      → Rule: Must have husband, wife, and minor children (< 18)")
                for member in family_members:
                    relation = member['Relation']
                    age = member['Age']
                    print(f"      → {relation}: {age} years old")
            else:
                print(f"   ❌ Family structure: NOT ELIGIBLE")
                print(f"      → Rule: Must have husband, wife, and minor children (< 18)")
                
                # Detailed analysis of what's wrong
                print(f"      → Detailed Analysis:")
                
                # Check for required family members
                required_relations = ['self', 'wife']
                found_relations = [m['Relation'] for m in family_members]
                
                # Check if self exists
                self_member = next((m for m in family_members if m['Relation'] == 'self'), None)
                if self_member:
                    print(f"         • Self: ✅ Found (age {self_member['Age']})")
                else:
                    print(f"         • Self: ❌ Missing")
                
                # Check if wife exists
                wife_member = next((m for m in family_members if m['Relation'] == 'wife'), None)
                if wife_member:
                    print(f"         • Wife: ✅ Found (age {wife_member['Age']})")
                else:
                    print(f"         • Wife: ❌ Missing")
                
                # Check children
                children = [m for m in family_members if m['Relation'] == 'child']
                if children:
                    print(f"         • Children: ✅ Found {len(children)} children")
                    for child in children:
                        age = child['Age']
                        if age < 18:
                            print(f"           - Child: ✅ Minor (age {age})")
                        else:
                            print(f"           - Child: ❌ Adult (age {age}) - Must be < 18")
                else:
                    print(f"         • Children: ❌ Missing")
                
                # Check for other family members that might be causing issues
                other_members = [m for m in family_members if m['Relation'] not in ['self', 'wife', 'child']]
                if other_members:
                    print(f"         • Other members: ⚠️ Found unexpected relations:")
                    for member in other_members:
                        print(f"           - {member['Relation']}: {member['Age']} years old")
                
                # Summary of what needs to be fixed
                print(f"      → Summary of Issues:")
                if not wife_member:
                    print(f"         • Missing wife")
                if not children:
                    print(f"         • Missing children")
                else:
                    adult_children = [c for c in children if c['Age'] >= 18]
                    if adult_children:
                        print(f"         • Has {len(adult_children)} adult children (must be minors < 18)")
                        for child in adult_children:
                            print(f"           - {child['Age']} years old is too old")
                
                # Show current family structure
                print(f"      → Current Family Structure:")
                for member in family_members:
                    relation = member['Relation']
                    age = member['Age']
                    print(f"         → {relation}: {age} years old")
            
            # Check key requirements
            print(f"\n📋 KEY REQUIREMENTS ANALYSIS:")
            key_requirements = [
                ('land_owner', 'Land Owner'),
                ('aadhaar_linked', 'Aadhaar Linked'),
                ('bank_account', 'Bank Account'),
                ('date_of_land_ownership', 'Land Ownership Date')
            ]
            
            all_reqs_passed = True
            for req_pred, req_name in key_requirements:
                req_results = list(self.prolog.query(f"{req_pred}({quoted_name}, Value)"))
                if req_results:
                    value = req_results[0]['Value']
                    if isinstance(value, bool):
                        status = "✅ PASS" if value else "❌ FAIL"
                        if not value:
                            all_reqs_passed = False
                    else:
                        status = "✅ PASS" if value else "❌ FAIL"
                        if not value:
                            all_reqs_passed = False
                    print(f"   {status} {req_name}: {value}")
                else:
                    print(f"   ❌ FAIL {req_name}: NOT FOUND")
                    all_reqs_passed = False
            
            # Check special provisions
            print(f"\n🔧 SPECIAL PROVISIONS ANALYSIS:")
            special_provisions_present = False
            try:
                # Check if special provisions exist
                region_special_results = list(self.prolog.query(f"region_special({quoted_name}, Region)"))
                has_cert_results = list(self.prolog.query(f"has_special_certificate({quoted_name}, HasCert)"))
                
                if region_special_results and has_cert_results:
                    region = region_special_results[0]['Region']
                    has_cert = has_cert_results[0]['HasCert']
                    
                    if has_cert:
                        cert_type_results = list(self.prolog.query(f"certificate_type({quoted_name}, CertType)"))
                        if cert_type_results:
                            cert_type = cert_type_results[0]['CertType']
                            print(f"   ✅ Special Provisions: PRESENT")
                            print(f"      → Region: {region}")
                            print(f"      → Certificate: {cert_type}")
                            print(f"      → Status: Validated")
                            special_provisions_present = True
                        else:
                            print(f"   ⚠️ Special Provisions: PARTIAL")
                            print(f"      → Region: {region}")
                            print(f"      → Certificate: Missing type")
                    else:
                        print(f"   ❌ Special Provisions: INVALID")
                        print(f"      → Region: {region}")
                        print(f"      → Certificate: Not present")
                else:
                    print(f"   ❌ Special Provisions: NOT APPLICABLE")
                    print(f"      → No special region or certificate requirements")
            except Exception as e:
                print(f"   ⚠️ Special Provisions: ERROR - {e}")
            
            # Final reasoning summary
            print(f"\n🎯 FINAL REASONING SUMMARY:")
            
            # Exclusions status
            if active_exclusions:
                print(f"   ❌ EXCLUSIONS: {len(active_exclusions)} active exclusions")
                print(f"      → {', '.join(active_exclusions)}")
            else:
                print(f"   ✅ EXCLUSIONS: All passed (no exclusions apply)")
            
            # Requirements status
            if all_reqs_passed:
                print(f"   ✅ REQUIREMENTS: All key requirements met")
            else:
                print(f"   ❌ REQUIREMENTS: Some key requirements failed")
            
            # Special provisions status
            if special_provisions_present:
                print(f"   ✅ SPECIAL PROVISIONS: Present and validated")
            else:
                print(f"   ❌ SPECIAL PROVISIONS: Not applicable or invalid")
            
            # Family structure status
            if family_results:
                print(f"   ✅ FAMILY STRUCTURE: Eligible")
            else:
                print(f"   ❌ FAMILY STRUCTURE: Not eligible")
            
            # Overall eligibility
            if eligible and not active_exclusions and family_results:
                print(f"\n🏆 OVERALL RESULT: ELIGIBLE")
                print(f"   → All exclusions passed")
                print(f"   → All requirements met")
                print(f"   → Family structure valid")
                if special_provisions_present:
                    print(f"   → Special provisions validated")
            else:
                print(f"\n❌ OVERALL RESULT: NOT ELIGIBLE")
                if active_exclusions:
                    print(f"   → Exclusions apply: {', '.join(active_exclusions)}")
                if not family_results:
                    print(f"   → Family structure fails")
                if not all_reqs_passed:
                    print(f"   → Some requirements failed")
            
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