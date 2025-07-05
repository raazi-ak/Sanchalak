#!/usr/bin/env python3
"""
Python Wrapper for Prolog-based Eligibility System
Provides a clean Python API for eligibility checking with reasoning capabilities.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json

try:
    from pyswip import Prolog
except ImportError:
    print("❌ PySWIP not installed. Install it with: pip install pyswip")
    print("Note: You also need SWI-Prolog installed on your system.")
    sys.exit(1)

# Add path for the mapper
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'pipeline'))
try:
    from efr_to_prolog_mapper import EFRToPrologMapper
except ImportError:
    print("⚠️  EFR to Prolog mapper not available, using fallback mode")
    EFRToPrologMapper = None

class PrologEligibilityChecker:
    """Python wrapper for Prolog-based eligibility checking with reasoning."""
    
    def __init__(self, prolog_file: str):
        """Initialize the eligibility checker with a Prolog file."""
        self.prolog_file = Path(prolog_file)
        if not self.prolog_file.exists():
            raise FileNotFoundError(f"Prolog file not found: {prolog_file}")
        
        self.prolog = Prolog()
        self._load_prolog_file()
    
    def _load_prolog_file(self):
        """Load the Prolog file into the Prolog engine."""
        try:
            # Load the Prolog file
            with open(self.prolog_file, 'r', encoding='utf-8') as f:
                prolog_code = f.read()
            
            # Execute the Prolog code
            self.prolog.consult(str(self.prolog_file))
            print(f"✅ Loaded Prolog system from: {self.prolog_file}")
            
        except Exception as e:
            print(f"❌ Error loading Prolog file: {e}")
            raise
    
    def add_person(self, name: str, data: Dict[str, Any]) -> bool:
        """Add a person with their data to the Prolog system."""
        try:
            # Use the EFR to Prolog mapper if available
            if EFRToPrologMapper is not None:
                mapper = EFRToPrologMapper()
                prolog_data = mapper.map_efr_to_prolog(data, name)
                
                # Validate the data
                is_valid, missing = mapper.validate_prolog_data(prolog_data)
                if not is_valid:
                    print(f"⚠️  Missing required fields: {missing}")
                
                # Create Prolog facts
                facts = mapper.create_prolog_facts(name, prolog_data)
                
                # Add each fact to Prolog
                for fact in facts:
                    try:
                        # Use assertz to add the fact (without the trailing period)
                        self.prolog.assertz(fact)
                    except Exception as fact_error:
                        print(f"⚠️  Could not add fact '{fact}': {fact_error}")
                        # Try alternative approach using query
                        try:
                            query = f"assertz({fact})"
                            list(self.prolog.query(query))
                        except Exception as alt_error:
                            print(f"⚠️  Alternative approach also failed for '{fact}': {alt_error}")
                
                print(f"✅ Added {len(facts)} facts for {name}")
                return True
                
            else:
                # Fallback to old method
                return self._add_person_fallback(name, data)
            
        except Exception as e:
            print(f"❌ Error adding person {name}: {e}")
            return False
    
    def _add_person_fallback(self, name: str, data: Dict[str, Any]) -> bool:
        """Fallback method for adding person data (old implementation)."""
        try:
            # Convert Python dict to Prolog list format, filtering out problematic fields
            prolog_data = []
            for key, value in data.items():
                # Skip None values, complex objects, and metadata fields
                if value is None:
                    continue
                if key in ['audio_metadata', 'extraction_metadata', 'pipeline_metadata', 'created_at', 'updated_at']:
                    continue
                if isinstance(value, (list, dict)):
                    # Convert lists to comma-separated strings
                    if isinstance(value, list):
                        value = ','.join(str(item) for item in value)
                    else:
                        continue  # Skip dicts
                
                # Clean the key and value for Prolog
                clean_key = str(key).replace("'", "").replace('"', "")
                clean_value = str(value).replace("'", "").replace('"', "")
                
                if isinstance(value, bool):
                    prolog_data.append(f"'{clean_key}'-{str(value).lower()}")
                elif isinstance(value, (int, float)):
                    prolog_data.append(f"'{clean_key}'-{value}")
                else:
                    prolog_data.append(f"'{clean_key}'-'{clean_value}'")
            
            prolog_list = f"[{', '.join(prolog_data)}]"
            
            # Add the person using Prolog
            query = f"add_test_person('{name}', {prolog_list})"
            result = list(self.prolog.query(query))
            
            return len(result) > 0
            
        except Exception as e:
            print(f"❌ Error adding person {name} (fallback): {e}")
            return False
    
    def check_eligibility(self, person_name: str) -> bool:
        """Check if a person is eligible."""
        try:
            result = list(self.prolog.query(f"eligible('{person_name}')"))
            return len(result) > 0
        except Exception as e:
            print(f"❌ Error checking eligibility for {person_name}: {e}")
            return False
    
    def explain_eligibility(self, person_name: str) -> Dict[str, Any]:
        """Get a detailed explanation of eligibility with reasoning."""
        try:
            # Capture the explanation output
            explanation = {
                'person': person_name,
                'eligible': False,
                'reasons': [],
                'failed_requirements': [],
                'exclusions': [],
                'special_provisions': []
            }
            
            # Check if eligible
            is_eligible = self.check_eligibility(person_name)
            explanation['eligible'] = is_eligible
            
            # Get detailed explanation using Prolog
            if is_eligible:
                # Get met requirements
                met_reqs = list(self.prolog.query(f"requirement('{person_name}', Req), requirement_met('{person_name}', Req)"))
                explanation['reasons'] = [str(req['Req']) for req in met_reqs]
                
                # Get special provisions
                special_provs = list(self.prolog.query(f"special_provision('{person_name}', Provision)"))
                explanation['special_provisions'] = [str(prov['Provision']) for prov in special_provs]
            else:
                # Get failed requirements
                failed_reqs = list(self.prolog.query(f"requirement('{person_name}', Req), not(requirement_met('{person_name}', Req))"))
                explanation['failed_requirements'] = [str(req['Req']) for req in failed_reqs]
                
                # Get exclusions
                exclusions = list(self.prolog.query(f"exclusion_applies('{person_name}', Excl)"))
                explanation['exclusions'] = [str(excl['Excl']) for excl in exclusions]
            
            return explanation
            
        except Exception as e:
            print(f"❌ Error getting explanation for {person_name}: {e}")
            return {
                'person': person_name,
                'error': str(e),
                'eligible': False
            }
    
    def check_requirements(self, person_name: str) -> Dict[str, bool]:
        """Check individual requirements for a person."""
        try:
            requirements = {}
            
            # Get all requirements and their status
            reqs = list(self.prolog.query(f"requirement('{person_name}', Req)"))
            for req in reqs:
                req_name = str(req['Req'])
                is_met = list(self.prolog.query(f"requirement_met('{person_name}', {req_name})"))
                requirements[req_name] = len(is_met) > 0
            
            return requirements
            
        except Exception as e:
            print(f"❌ Error checking requirements for {person_name}: {e}")
            return {}
    
    def show_exclusions(self, person_name: str) -> List[str]:
        """Show exclusion reasons for a person."""
        try:
            exclusions = list(self.prolog.query(f"exclusion_applies('{person_name}', Excl)"))
            return [str(excl['Excl']) for excl in exclusions]
        except Exception as e:
            print(f"❌ Error checking exclusions for {person_name}: {e}")
            return []
    
    def get_scheme_info(self) -> Dict[str, str]:
        """Get information about the scheme."""
        try:
            info = {}
            
            # Get scheme name
            name_result = list(self.prolog.query("scheme_name(Name)"))
            if name_result:
                info['name'] = str(name_result[0]['Name'])
            
            # Get scheme description
            desc_result = list(self.prolog.query("scheme_description(Desc)"))
            if desc_result:
                info['description'] = str(desc_result[0]['Desc'])
            
            # Get scheme source
            source_result = list(self.prolog.query("scheme_source(Source)"))
            if source_result:
                info['source'] = str(source_result[0]['Source'])
            
            return info
            
        except Exception as e:
            print(f"❌ Error getting scheme info: {e}")
            return {}
    
    def run_test_system(self) -> bool:
        """Run the built-in test system."""
        try:
            result = list(self.prolog.query("test_system"))
            return len(result) > 0
        except Exception as e:
            print(f"❌ Error running test system: {e}")
            return False

def main():
    """Demo the Prolog eligibility checker."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Python wrapper for Prolog-based eligibility checking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python prolog_eligibility_wrapper.py ../outputs/pm-kisan/REFERENCE_prolog_system.pl
  python prolog_eligibility_wrapper.py -f ../outputs/pm-kisan/REFERENCE_prolog_system.pl -p ramesh
        """
    )
    
    parser.add_argument(
        'prolog_file',
        nargs='?',
        help='Path to the Prolog file (default: ../outputs/pm-kisan/REFERENCE_prolog_system.pl)'
    )
    
    parser.add_argument(
        '-f', '--file',
        dest='prolog_file_alt',
        help='Alternative way to specify Prolog file path'
    )
    
    parser.add_argument(
        '-p', '--person',
        help='Person name to check eligibility for'
    )
    
    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help='Run the test system'
    )
    
    args = parser.parse_args()
    
    # Determine Prolog file path
    prolog_path = args.prolog_file or args.prolog_file_alt or '../outputs/pm-kisan/REFERENCE_prolog_system.pl'
    
    try:
        # Initialize the checker
        checker = PrologEligibilityChecker(prolog_path)
        
        # Get scheme info
        scheme_info = checker.get_scheme_info()
        print(f"\n🤖 {scheme_info.get('name', 'Government Scheme')} Eligibility System")
        print(f"📄 {scheme_info.get('description', 'No description')}")
        print("=" * 60)
        
        if args.test:
            print("\n🧪 Running test system...")
            checker.run_test_system()
        
        elif args.person:
            person_name = args.person
            
            # Add example person data (you can modify this)
            person_data = {
                'land_owner': True,
                'date_of_land_ownership': '2018-01-01',
                'aadhaar_linked': True,
                'bank_account': True,
                'category': 'general',
                'family_definition': 'husband_wife_minor_children',
                'region': 'general'
            }
            
            print(f"\n👤 Checking eligibility for: {person_name}")
            print(f"📋 Data: {json.dumps(person_data, indent=2)}")
            
            # Add person and check eligibility
            if checker.add_person(person_name, person_data):
                explanation = checker.explain_eligibility(person_name)
                
                print(f"\n🎯 Result: {'✅ ELIGIBLE' if explanation['eligible'] else '❌ NOT ELIGIBLE'}")
                
                if explanation['eligible']:
                    print(f"✅ Reasons: {', '.join(explanation['reasons'])}")
                    if explanation['special_provisions']:
                        print(f"🔶 Special provisions: {', '.join(explanation['special_provisions'])}")
                else:
                    if explanation['failed_requirements']:
                        print(f"❌ Failed requirements: {', '.join(explanation['failed_requirements'])}")
                    if explanation['exclusions']:
                        print(f"🚫 Exclusions: {', '.join(explanation['exclusions'])}")
            else:
                print(f"❌ Failed to add person {person_name}")
        
        else:
            print("\n📖 Usage:")
            print("  python prolog_eligibility_wrapper.py -p <person_name>")
            print("  python prolog_eligibility_wrapper.py -t")
            print("\n💡 Example:")
            print("  python prolog_eligibility_wrapper.py -p ramesh")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 