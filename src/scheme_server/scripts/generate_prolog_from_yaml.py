#!/usr/bin/env python3
"""
Prolog-based Eligibility System Generator from Canonical YAML
Generates Prolog facts and rules for government scheme eligibility with reasoning capabilities.
"""

import yaml
import re
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

class PrologGenerator:
    def __init__(self, yaml_path: str, output_path: str = None):
        self.yaml_path = Path(yaml_path)
        
        # If no output path specified, create it in the same directory as the YAML file
        if output_path:
            self.output_path = Path(output_path)
        else:
            # Generate output filename based on scheme name
            yaml_dir = self.yaml_path.parent
            scheme_name = self.yaml_path.stem.replace('rules_canonical_', '').replace('_REFERENCE', '')
            self.output_path = yaml_dir / f"{scheme_name}_prolog_system.pl"
        
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
    
    def clean_predicate_name(self, name: str) -> str:
        """Convert names to valid Prolog predicate names."""
        # Remove quotes and clean the name
        name = name.strip('"\'')
        # Replace spaces and special chars with underscores
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it starts with a letter
        if name and not name[0].isalpha():
            name = 'field_' + name
        return name.lower()
    
    def escape_prolog_string(self, text: str) -> str:
        """Escape special characters for Prolog strings."""
        if not isinstance(text, str):
            return str(text)
        # Escape single quotes and backslashes
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "\\'")
        # Replace problematic Unicode characters
        text = text.replace("–", "-")  # en dash to hyphen
        text = text.replace("—", "-")  # em dash to hyphen
        text = text.replace("'", "'")  # smart quote to regular
        text = text.replace("'", "'")  # smart quote to regular
        text = text.replace('"', '"')  # smart quote to regular
        text = text.replace('"', '"')  # smart quote to regular
        return text
    
    def generate_header(self) -> str:
        """Generate Prolog file header."""
        scheme_name = self.scheme.get('name', 'Government Scheme')
        description = self.escape_prolog_string(self.scheme.get('description', 'No description available'))
        source_url = self.scheme.get('metadata', {}).get('source_url', 'Unknown')
        
        return f"""% -*- coding: utf-8 -*-
% Prolog Eligibility System for {scheme_name}
% Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
% Source: {source_url}
%
% This system provides eligibility checking with reasoning capabilities.
% Use the following predicates:
%   - eligible(Person) : Check if a person is eligible
%   - explain_eligibility(Person) : Get detailed explanation
%   - check_requirements(Person) : Check specific requirements
%   - show_exclusions(Person) : Show exclusion reasons

:- dynamic person/2.
:- dynamic requirement_met/2.
:- dynamic exclusion_applies/2.

% Scheme Information
scheme_name('{scheme_name}').
scheme_description('{description}').
scheme_source('{source_url}').

"""
    
    def generate_eligibility_rules(self) -> str:
        """Generate Prolog rules for eligibility checking."""
        rules = self.scheme.get('eligibility', {}).get('rules', [])
        code = "\n% Eligibility Rules\n"
        
        # Generate the main eligibility rule
        code += """
% Main eligibility rule
eligible(Person) :-
    person(Person, _),
    not(excluded(Person)),
    all_requirements_met(Person).

% Check if person is excluded
excluded(Person) :-
    exclusion_applies(Person, _).

% Check if all requirements are met
all_requirements_met(Person) :-
    findall(Req, requirement(Person, Req), Requirements),
    Requirements \\= [],
    maplist(requirement_met(Person), Requirements).

% Individual requirement checking
requirement_met(Person, Req) :-
    requirement(Person, Req),
    check_requirement(Person, Req).

"""
        
        # Generate specific requirement rules
        for i, rule in enumerate(rules):
            field = self.clean_predicate_name(rule.get('field', f'field_{i}'))
            operator = rule.get('operator', '==').strip('"')
            value = rule.get('value')
            data_type = rule.get('data_type', 'string')
            description = self.escape_prolog_string(rule.get('description', f'Check {field}'))
            
            # Generate requirement fact
            code += f"""
% Requirement: {description}
requirement(Person, {field}) :-
    person(Person).

check_requirement(Person, {field}) :-
    {field}(Person, Value),
    check_{field}_condition(Value).

check_{field}_condition(Value) :-
"""
            
            # Generate condition checking based on operator and data type
            if operator == '==':
                if data_type == 'boolean':
                    code += f"    Value = {str(value).lower()}.\n"
                elif data_type in ['number', 'integer']:
                    code += f"    Value = {value}.\n"
                else:
                    code += f"    Value = '{self.escape_prolog_string(str(value))}'.\n"
            elif operator == '!=':
                if data_type == 'boolean':
                    code += f"    Value \\= {str(value).lower()}.\n"
                elif data_type in ['number', 'integer']:
                    code += f"    Value \\= {value}.\n"
                else:
                    code += f"    Value \\= '{self.escape_prolog_string(str(value))}'.\n"
            elif operator in ['>', '<', '>=', '<=']:
                code += f"    Value {operator} {value}.\n"
            elif operator == 'in':
                if isinstance(value, list):
                    value_list = [f"'{self.escape_prolog_string(str(v))}'" for v in value]
                    code += f"    member(Value, [{', '.join(value_list)}]).\n"
                else:
                    code += f"    Value = '{self.escape_prolog_string(str(value))}'.\n"
            elif operator == 'not in':
                if isinstance(value, list):
                    value_list = [f"'{self.escape_prolog_string(str(v))}'" for v in value]
                    code += f"    not(member(Value, [{', '.join(value_list)}])).\n"
                else:
                    code += f"    Value \\= '{self.escape_prolog_string(str(value))}'.\n"
            else:
                # Default to equality
                code += f"    Value = '{self.escape_prolog_string(str(value))}'.\n"
        
        return code
    
    def generate_exclusion_rules(self) -> str:
        """Generate Prolog rules for exclusion criteria."""
        exclusions = self.scheme.get('eligibility', {}).get('exclusion_criteria', [])
        code = "\n% Exclusion Rules\n"
        
        for i, exclusion in enumerate(exclusions):
            exclusion_id = f"exclusion_{i+1}"
            exclusion_text = self.escape_prolog_string(exclusion)
            
            code += f"""
% Exclusion: {exclusion_text}
exclusion_applies(Person, {exclusion_id}) :-
    person(Person),
    check_{exclusion_id}(Person).

check_{exclusion_id}(Person) :-
    % Add specific exclusion logic here
    % For now, this is a placeholder
    fail.
"""
        
        return code
    
    def generate_special_provisions(self) -> str:
        """Generate Prolog rules for special provisions."""
        specials = self.scheme.get('special_provisions', [])
        code = "\n% Special Provisions\n"
        
        for special in specials:
            region = special.get('region', 'Unknown')
            description = self.escape_prolog_string(special.get('description', 'No description'))
            region_id = self.clean_predicate_name(region)
            
            code += f"""
% Special provision for {region}
special_provision(Person, '{region_id}') :-
    person(Person),
    region(Person, '{self.escape_prolog_string(region)}'),
    apply_{region_id}_provision(Person).

apply_{region_id}_provision(Person) :-
    % {description}
    % Add specific provision logic here
    true.
"""
        
        return code
    
    def generate_utility_predicates(self) -> str:
        """Generate utility predicates for data handling and explanation."""
        return """
% Utility predicates

% Get field value from person data (atomic facts)
get_field_value(Person, Field, Value) :-
    call(Field, Person, Value).

% Explanation predicates
explain_eligibility(Person) :-
    write('=== Eligibility Explanation for '), write(Person), write(' ==='), nl,
    (   eligible(Person)
    ->  write('✅ ELIGIBLE'), nl,
        write('Reasons:'), nl,
        findall(Req, (requirement(Person, Req), requirement_met(Person, Req)), MetReqs),
        maplist(write_requirement, MetReqs),
        (   special_provision(Person, Provision)
        ->  write('🔶 Special provision applied: '), write(Provision), nl
        ;   true
        )
    ;   write('❌ NOT ELIGIBLE'), nl,
        write('Reasons:'), nl,
        (   excluded(Person)
        ->  findall(Excl, exclusion_applies(Person, Excl), Exclusions),
            maplist(write_exclusion, Exclusions)
        ;   findall(Req, (requirement(Person, Req), not(requirement_met(Person, Req))), FailedReqs),
            maplist(write_failed_requirement, FailedReqs)
        )
    ).

write_requirement(Req) :-
    write('  ✅ '), write(Req), nl.

write_failed_requirement(Req) :-
    write('  ❌ '), write(Req), nl.

write_exclusion(Excl) :-
    write('  🚫 '), write(Excl), nl.

% Check specific requirements
check_requirements(Person) :-
    write('=== Requirements Check for '), write(Person), write(' ==='), nl,
    findall(Req, requirement(Person, Req), Requirements),
    maplist(check_and_report_requirement(Person), Requirements).

check_and_report_requirement(Person, Req) :-
    (   requirement_met(Person, Req)
    ->  write('✅ '), write(Req), nl
    ;   write('❌ '), write(Req), nl
    ).

% Show exclusions
show_exclusions(Person) :-
    write('=== Exclusions Check for '), write(Person), write(' ==='), nl,
    (   excluded(Person)
    ->  findall(Excl, exclusion_applies(Person, Excl), Exclusions),
        maplist(write_exclusion, Exclusions)
    ;   write('✅ No exclusions apply'), nl
    ).

% Show all facts for a person
show_person_facts(Person) :-
    write('=== Facts for '), write(Person), write(' ==='), nl,
    findall(Field-Value, (current_predicate(Field/2), call(Field, Person, Value)), Facts),
    maplist(write_fact, Facts).

write_fact(Field-Value) :-
    write('  '), write(Field), write(': '), write(Value), nl.

"""
    
    def generate_example_usage(self) -> str:
        """Generate example usage and test cases."""
        return """
% Example usage and test cases

% Add a test person with atomic facts
add_test_person(Name) :-
    assertz(person(Name)).

% Add individual facts for a person
add_person_fact(Person, Field, Value) :-
    assertz(Field(Person, Value)).

% Example: Add a farmer
example_farmer :-
    add_test_person('ramesh'),
    add_person_fact('ramesh', land_owner, true),
    add_person_fact('ramesh', land_size_acres, 5.0),
    add_person_fact('ramesh', land_ownership, 'owned'),
    add_person_fact('ramesh', bank_account, true),
    add_person_fact('ramesh', state, 'karnataka'),
    add_person_fact('ramesh', family_size, 4),
    add_person_fact('ramesh', age, 45).

% Example: Add an excluded person
example_excluded_person :-
    add_test_person('suresh'),
    add_person_fact('suresh', land_owner, false),
    add_person_fact('suresh', land_size_acres, 0.0),
    add_person_fact('suresh', land_ownership, 'unknown'),
    add_person_fact('suresh', bank_account, true),
    add_person_fact('suresh', state, 'karnataka'),
    add_person_fact('suresh', family_size, 3),
    add_person_fact('suresh', age, 35).

% Test the system
test_system :-
    write('=== Testing PM-KISAN Eligibility System ==='), nl, nl,
    example_farmer,
    example_excluded_person,
    write('Testing eligible person:'), nl,
    explain_eligibility('ramesh'), nl,
    write('Testing ineligible person:'), nl,
    explain_eligibility('suresh'), nl.

"""
    
    def generate(self) -> bool:
        """Generate the complete Prolog eligibility system."""
        if not self.load_yaml():
            return False
        
        try:
            # Build the complete Prolog code
            code = (
                self.generate_header() +
                self.generate_eligibility_rules() +
                self.generate_exclusion_rules() +
                self.generate_special_provisions() +
                self.generate_utility_predicates() +
                self.generate_example_usage()
            )
            
            # Write to file
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            print(f"✅ Generated Prolog eligibility system at: {self.output_path}")
            print(f"📊 Scheme: {self.scheme.get('name', 'Unknown')}")
            print(f"📋 Rules: {len(self.scheme.get('eligibility', {}).get('rules', []))}")
            print(f"🚫 Exclusions: {len(self.scheme.get('eligibility', {}).get('exclusion_criteria', []))}")
            print(f"🔶 Special Provisions: {len(self.scheme.get('special_provisions', []))}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error generating Prolog system: {e}")
            return False

def main():
    """Main function to run the generator."""
    parser = argparse.ArgumentParser(
        description="Generate Prolog eligibility system from canonical YAML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_prolog_from_yaml.py ../outputs/pm-kisan/rules_canonical_REFERENCE.yaml
  python generate_prolog_from_yaml.py -i ../outputs/pm-kisan/rules_canonical_REFERENCE.yaml -o ../outputs/pm-kisan/pm_kisan_prolog.pl
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
        help='Output file path for the generated Prolog system (default: same directory as input YAML)'
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
    generator = PrologGenerator(input_path, args.output)
    
    if generator.generate():
        print("\n✅ Prolog eligibility system generated successfully!")
        print(f"📁 Output file: {generator.output_path}")
        print("\nTo use the Prolog system:")
        print(f"1. Install SWI-Prolog: https://www.swi-prolog.org/download/stable")
        print(f"2. Load the file: swipl {generator.output_path}")
        print(f"3. Run tests: test_system.")
        print(f"4. Check eligibility: explain_eligibility('ramesh').")
    else:
        print("\n❌ Failed to generate Prolog eligibility system.")
        sys.exit(1)

if __name__ == "__main__":
    main() 