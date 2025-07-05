#!/usr/bin/env python3
"""
Enhanced Experta Expert System Generator from Canonical YAML
Generates a complete Experta knowledge engine from government scheme YAML data.
"""

import yaml
import re
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

class ExpertaGenerator:
    def __init__(self, yaml_path: str, output_path: str = None):
        self.yaml_path = Path(yaml_path)
        
        # If no output path specified, create it in the same directory as the YAML file
        if output_path:
            self.output_path = Path(output_path)
        else:
            # Generate output filename based on scheme name
            yaml_dir = self.yaml_path.parent
            scheme_name = self.yaml_path.stem.replace('rules_canonical_', '').replace('_REFERENCE', '')
            self.output_path = yaml_dir / f"{scheme_name}_experta_system.py"
        
        self.data = None
        self.scheme = None
        
    def load_yaml(self):
        """Load and validate the canonical YAML file."""
        try:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                self.data = yaml.safe_load(f)
            
            if not self.data or 'schemes' not in self.data:
                raise ValueError("Invalid YAML structure: missing 'schemes' key")
            
            self.scheme = self.data['schemes'][0]
            print(f"✅ Loaded scheme: {self.scheme.get('name', 'Unknown')}")
            return True
        except Exception as e:
            print(f"❌ Error loading YAML: {e}")
            return False
    
    def clean_field_name(self, field: str) -> str:
        """Convert field names to valid Python identifiers."""
        # Remove quotes and clean the field name
        field = field.strip('"\'')
        # Replace spaces and special chars with underscores
        field = re.sub(r'[^a-zA-Z0-9_]', '_', field)
        # Ensure it starts with a letter
        if field and not field[0].isalpha():
            field = 'field_' + field
        return field.lower()
    
    def python_type(self, yaml_type: str) -> str:
        """Convert YAML data types to Python types."""
        type_map = {
            'boolean': 'bool',
            'date': 'str',
            'string': 'str',
            'number': 'float',
            'integer': 'int'
        }
        return type_map.get(yaml_type, 'str')
    
    def generate_imports(self) -> str:
        """Generate import statements."""
        return '''# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Generated Experta Expert System for {scheme_name}
Generated on: {timestamp}
Source: {source_url}
"""

from experta import *
from datetime import datetime
import re
from typing import Dict, List, Any

'''.format(
            scheme_name=self.scheme.get('name', 'Government Scheme'),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            source_url=self.scheme.get('metadata', {}).get('source_url', 'Unknown')
        )
    
    def generate_facts(self) -> str:
        """Generate Fact classes."""
        return '''
class UserData(Fact):
    """User data for eligibility assessment"""
    pass

class SchemeInfo(Fact):
    """Scheme information and metadata"""
    pass

class EligibilityResult(Fact):
    """Eligibility assessment result"""
    pass

class ExclusionReason(Fact):
    """Reason for exclusion"""
    pass

class SpecialProvision(Fact):
    """Special provision information"""
    pass

'''
    
    def generate_engine_class(self) -> str:
        """Generate the main knowledge engine class."""
        scheme_name = self.scheme.get('name', 'GovernmentScheme').replace('-', '').replace(' ', '')
        
        # Clean metadata for Python code
        metadata = self.scheme.get('metadata', {})
        metadata_str = repr(metadata)
        
        # Clean special provisions for Python code
        special_provisions = self.scheme.get('special_provisions', [])
        special_provisions_str = repr(special_provisions)
        
        return f'''
class {scheme_name}EligibilityEngine(KnowledgeEngine):
    """
    Expert system for {self.scheme.get('name', 'Government Scheme')} eligibility assessment.
    
    This system evaluates eligibility based on:
    - Eligibility rules and criteria
    - Exclusion criteria
    - Special provisions for specific regions
    - Required documents and benefits
    """
    
    def __init__(self):
        super().__init__()
        self.eligibility_result = None
        self.exclusion_reasons = []
        self.special_provisions = []
        self.missing_documents = []
    
    @DefFacts()
    def _initial_facts(self):
        """Initialize scheme information and start eligibility check."""
        # Scheme metadata
        metadata = {metadata_str}
        yield SchemeInfo(
            name={repr(self.scheme.get('name', 'Unknown'))},
            description={repr(self.scheme.get('description', 'No description available'))},
            source_url={repr(self.scheme.get('metadata', {}).get('source_url', 'Unknown'))},
            **metadata
        )
        
        # Start eligibility assessment
        yield Fact(action='assess_eligibility')
        
        # Initialize special provisions
        for provision in {special_provisions_str}:
            yield SpecialProvision(
                region=provision.get('region', 'Unknown'),
                description=provision.get('description', 'No description')
            )
'''
    
    def generate_eligibility_rules(self) -> str:
        """Generate rules for eligibility assessment."""
        rules = self.scheme.get('eligibility', {}).get('rules', [])
        code = "\n    # Eligibility Rules\n"
        
        for i, rule in enumerate(rules):
            field = self.clean_field_name(rule.get('field', f'field_{i}'))
            operator = rule.get('operator', '==').strip('"')
            value = rule.get('value')
            data_type = rule.get('data_type', 'string')
            description = rule.get('description', f'Check {field}')
            
            # Generate rule for asking user input
            code += f'''
    @Rule(Fact(action='assess_eligibility'),
          NOT(UserData({field}=W())))
    def ask_{field}(self):
        """Ask user for {field} information."""
        try:
            user_input = input(f"{description}: ")
            # Convert input based on data type
            if "{data_type}" == "boolean":
                value = user_input.lower() in ['true', 'yes', '1', 'y']
            elif "{data_type}" == "date":
                value = user_input
            elif "{data_type}" == "number":
                value = float(user_input)
            elif "{data_type}" == "integer":
                value = int(user_input)
            else:
                value = user_input
            
            self.declare(UserData({field}=value))
            print(f"✓ Recorded {field}: {{value}}")
        except ValueError as e:
            print(f"❌ Invalid input for {field}: {{e}}")
            self.declare(UserData({field}=None))
'''
        
        # Generate main eligibility rule
        # Clean rules for Python code
        rules_str = repr(rules)
        
        code += f'''
    @Rule(Fact(action='assess_eligibility'),
          salience=1)
    def check_eligibility_criteria(self):
        """Check all eligibility criteria."""
        print("\\n🔍 Checking eligibility criteria...")
        
        # Get all user data
        user_data = {{}}
        for fact in self.facts:
            if isinstance(fact, UserData):
                user_data[fact[0]] = fact[1]
        
        # Check each eligibility rule
        all_eligible = True
        for rule in {rules_str}:
            field = rule.get('field', 'unknown')
            operator = rule.get('operator', '==')
            expected_value = rule.get('value')
            data_type = rule.get('data_type', 'string')
            
            user_value = user_data.get(field)
            if user_value is None:
                print(f"⚠️ Missing data for {{field}}")
                all_eligible = False
                continue
            
            # Check condition
            condition_met = self._check_condition(user_value, operator, expected_value, data_type)
            if not condition_met:
                print(f"❌ Failed: {{field}} {{operator}} {{expected_value}} (got: {{user_value}})")
                all_eligible = False
            else:
                print(f"✅ Passed: {{field}} {{operator}} {{expected_value}}")
        
        if all_eligible:
            self.declare(EligibilityResult(status="ELIGIBLE"))
        else:
            self.declare(EligibilityResult(status="INELIGIBLE"))
    
    def _check_condition(self, user_value, operator, expected_value, data_type):
        """Check if a condition is met."""
        try:
            if data_type == "boolean":
                user_value = bool(user_value)
            elif data_type == "number":
                user_value = float(user_value)
                expected_value = float(expected_value)
            elif data_type == "integer":
                user_value = int(user_value)
                expected_value = int(expected_value)
            
            if operator == "==":
                return user_value == expected_value
            elif operator == "!=":
                return user_value != expected_value
            elif operator == ">":
                return user_value > expected_value
            elif operator == "<":
                return user_value < expected_value
            elif operator == ">=":
                return user_value >= expected_value
            elif operator == "<=":
                return user_value <= expected_value
            elif operator == "in":
                if isinstance(expected_value, list):
                    return user_value in expected_value
                else:
                    return user_value in [expected_value]
            elif operator == "not in":
                if isinstance(expected_value, list):
                    return user_value not in expected_value
                else:
                    return user_value not in [expected_value]
            else:
                return user_value == expected_value  # Default fallback
        except (ValueError, TypeError):
            return False
'''
        
        return code
    
    def generate_exclusion_rules(self) -> str:
        """Generate rules for exclusion criteria."""
        exclusions = self.scheme.get('eligibility', {}).get('exclusion_criteria', [])
        code = "\n    # Exclusion Rules\n"
        
        for i, exclusion in enumerate(exclusions):
            exclusion_id = f"exclusion_{i+1}"
            code += f'''
    @Rule(Fact(action='assess_eligibility'),
          UserData({exclusion_id}=True))
    def {exclusion_id}_rule(self):
        """Check for exclusion: {exclusion}"""
        self.declare(ExclusionReason(
            reason="{exclusion}",
            category="exclusion_criteria"
        ))
        print(f"❌ Excluded: {exclusion}")
'''
        
        return code
    
    def generate_special_provision_rules(self) -> str:
        """Generate rules for special provisions."""
        specials = self.scheme.get('special_provisions', [])
        code = "\n    # Special Provision Rules\n"
        
        for special in specials:
            region = special.get('region', 'Unknown')
            description = special.get('description', 'No description')
            region_id = self.clean_field_name(region)
            region_doc = region.replace('"', '\"')
            
            code += f'''
    @Rule(Fact(action='assess_eligibility'),
          UserData(region={repr(region)}))
    def special_provision_{region_id}(self):
        # Apply special provision for {region_doc}
        self.declare(SpecialProvision(
            region={repr(region)},
            description={repr(description)},
            applied=True
        ))
        print(f"🔶 Special provision applied for {region}")
        print(f"   {description!r}")
'''
        
        return code
    
    def generate_result_rules(self) -> str:
        """Generate rules for final result processing."""
        # Clean data for Python code
        benefits = repr(self.scheme.get('benefits', []))
        documents = repr(self.scheme.get('documents', []))
        application_modes = repr(self.scheme.get('application_modes', []))
        
        return f'''
    @Rule(EligibilityResult(status="ELIGIBLE"))
    def process_eligible_result(self):
        """Process eligible result and show benefits."""
        print("\\n🎉 ELIGIBILITY RESULT: ELIGIBLE")
        print("=" * 50)
        
        # Show benefits
        benefits = {benefits}
        if benefits:
            print("\\n💰 Benefits:")
            for benefit in benefits:
                if isinstance(benefit, dict):
                    print(f"  • {{benefit.get('type', 'Benefit')}}: {{benefit.get('description', 'No description')}}")
                    if 'amount' in benefit:
                        print(f"    Amount: {{benefit.get('amount')}} {{benefit.get('currency', '')}}")
                    if 'frequency' in benefit:
                        print(f"    Frequency: {{benefit.get('frequency')}}")
                else:
                    print(f"  • {{benefit}}")
        
        # Show required documents
        documents = {documents}
        if documents:
            print("\\n📋 Required Documents:")
            for doc in documents:
                print(f"  • {{doc}}")
        
        # Show application modes
        application_modes = {application_modes}
        if application_modes:
            print("\\n📝 Application Modes:")
            for mode in application_modes:
                print(f"  • {{mode}}")
        
        print("\\n" + "=" * 50)
        self.halt()
    
    @Rule(EligibilityResult(status="INELIGIBLE"))
    def process_ineligible_result(self):
        """Process ineligible result and show reasons."""
        print("\\n❌ ELIGIBILITY RESULT: NOT ELIGIBLE")
        print("=" * 50)
        
        # Show exclusion reasons
        for fact in self.facts:
            if isinstance(fact, ExclusionReason):
                print(f"  • {{fact['reason']}}")
        
        print("\\n" + "=" * 50)
        self.halt()
    
    @Rule(ExclusionReason())
    def process_exclusion(self):
        """Process exclusion reasons."""
        for fact in self.facts:
            if isinstance(fact, ExclusionReason):
                print(f"❌ Exclusion: {{fact['reason']}}")
                self.declare(EligibilityResult(
                    status="INELIGIBLE",
                    reason=f"Excluded: {{fact['reason']}}"
                ))
                self.halt()
'''
    
    def generate_main_function(self) -> str:
        """Generate the main function to run the expert system."""
        scheme_name = self.scheme.get('name', 'GovernmentScheme').replace('-', '').replace(' ', '')
        return f'''
def main():
    """Main function to run the {self.scheme.get('name', 'Government Scheme')} eligibility assessment."""
    print("=" * 60)
    print(f"🤖 {self.scheme.get('name', 'Government Scheme')} Eligibility Assessment")
    print("=" * 60)
    print(f"📄 Description: {self.scheme.get('description', 'No description available')}")
    print(f"🏛️ Ministry: {self.scheme.get('ministry', 'Unknown')}")
    print(f"📅 Launched: {self.scheme.get('launched_on', 'Unknown')}")
    print("=" * 60)
    
    # Create and run the expert system
    engine = {scheme_name}EligibilityEngine()
    engine.reset()
    engine.run()
    
    print("\\n✅ Assessment complete!")

if __name__ == "__main__":
    main()
'''
    
    def generate(self) -> bool:
        """Generate the complete Experta expert system."""
        if not self.load_yaml():
            return False
        
        try:
            # Build the complete code
            code = (
                self.generate_imports() +
                self.generate_facts() +
                self.generate_engine_class() +
                self.generate_eligibility_rules() +
                self.generate_exclusion_rules() +
                self.generate_special_provision_rules() +
                self.generate_result_rules() +
                self.generate_main_function()
            )
            
            # Write to file
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            print(f"✅ Generated Experta expert system at: {self.output_path}")
            print(f"📊 Scheme: {self.scheme.get('name', 'Unknown')}")
            print(f"📋 Rules: {len(self.scheme.get('eligibility', {}).get('rules', []))}")
            print(f"🚫 Exclusions: {len(self.scheme.get('eligibility', {}).get('exclusion_criteria', []))}")
            print(f"🔶 Special Provisions: {len(self.scheme.get('special_provisions', []))}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error generating Experta system: {e}")
            return False

def main():
    """Main function to run the generator."""
    parser = argparse.ArgumentParser(
        description="Generate Experta expert system from canonical YAML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_experta_from_yaml.py ../outputs/pm-kisan/rules_canonical_REFERENCE.yaml
  python generate_experta_from_yaml.py -i ../outputs/pm-kisan/rules_canonical_REFERENCE.yaml -o ../outputs/pm-kisan/pm_kisan_experta.py
        """
    )
    
    parser.add_argument(
        'input_yaml',
        nargs='?',
        help='Path to the canonical YAML file (default: ../outputs/pm-kisan/rules_canonical_REFERENCE.yaml)'
    )
    
    parser.add_argument(
        '-i', '--input',
        dest='input_yaml_alt',
        help='Alternative way to specify input YAML file path'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file path for the generated Experta system (default: same directory as input YAML)'
    )
    
    args = parser.parse_args()
    
    # Determine input file path
    input_path = args.input_yaml or args.input_yaml_alt or '../outputs/pm-kisan/rules_canonical_REFERENCE.yaml'
    
    # Validate input file exists
    if not Path(input_path).exists():
        print(f"❌ Error: Input file '{input_path}' not found!")
        print(f"Current working directory: {Path.cwd()}")
        sys.exit(1)
    
    # Create generator
    generator = ExpertaGenerator(input_path, args.output)
    
    if generator.generate():
        print("\n✅ Experta expert system generated successfully!")
        print(f"📁 Output file: {generator.output_path}")
        print("\nTo run the expert system:")
        print(f"python {generator.output_path}")
    else:
        print("\n❌ Failed to generate Experta expert system.")
        sys.exit(1)

if __name__ == "__main__":
    main() 