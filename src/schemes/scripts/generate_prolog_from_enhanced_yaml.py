#!/usr/bin/env python3
"""
Generate Prolog facts, rules, and Pydantic data classes from enhanced canonical YAML.
This script is completely data-driven and intelligently handles complex logic from the YAML.
"""

import yaml
import json
import argparse
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from enum import Enum


class IntelligentPrologGenerator:
    def __init__(self, yaml_file: str):
        """Initialize with enhanced canonical YAML file."""
        self.yaml_file = yaml_file
        self.scheme_data = self._load_yaml()
        self.data_model = self.scheme_data['schemes'][0]['data_model']
        self.scheme = self.scheme_data['schemes'][0]
        
    def _load_yaml(self) -> Dict[str, Any]:
        """Load and parse the YAML file."""
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _clean_string(self, value: str) -> str:
        """Clean string for Prolog compatibility."""
        if not isinstance(value, str):
            return str(value)
        
        # Remove quotes and clean
        value = value.strip().strip('"\'')
        
        # Handle special characters
        value = value.replace('\\', '\\\\')
        value = value.replace("'", "\\'")
        value = value.replace('"', '\\"')
        
        # Handle Unicode characters
        value = value.replace('–', '-')  # en dash to hyphen
        value = value.replace('—', '-')  # em dash to hyphen
        value = value.replace('…', '...')  # ellipsis
        
        return value
    
    def _get_all_fields(self) -> Dict[str, Dict[str, Any]]:
        """Extract all fields from the data model."""
        fields = {}
        
        for section_name, section_data in self.data_model.items():
            if isinstance(section_data, dict):
                for field_name, field_config in section_data.items():
                    if isinstance(field_config, dict) and 'type' in field_config:
                        fields[f"{section_name}_{field_name}"] = {
                            'section': section_name,
                            'field': field_name,
                            **field_config
                        }
        
        return fields
    
    def _get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        required_fields = []
        fields = self._get_all_fields()
        
        for field_key, field_config in fields.items():
            if field_config.get('required', False):
                required_fields.append(field_key)
        
        return required_fields
    
    def _generate_prolog_facts_from_yaml(self) -> List[str]:
        """Generate Prolog facts from YAML data model."""
        facts = []
        fields = self._get_all_fields()
        
        for field_key, field_config in fields.items():
            if 'prolog_fact' in field_config:
                fact_template = field_config['prolog_fact']
                description = field_config.get('description', field_key)
                
                facts.append(f"    % {description}")
                facts.append(f"    % {fact_template}.")
                
                # Handle complex types with multiple Prolog facts
                if field_config.get('type') == 'list_of_objects' and 'prolog_facts' in field_config:
                    for fact in field_config['prolog_facts']:
                        facts.append(f"    % {fact}.")
        
        return facts
    
    def _generate_eligibility_rules_from_yaml(self) -> List[str]:
        """Generate eligibility rules from YAML data model."""
        rules = []
        
        # Core eligibility rule based on required fields
        required_fields = self._get_required_fields()
        required_conditions = []
        
        for field_key in required_fields:
            field_config = self._get_all_fields()[field_key]
            if 'prolog_fact' in field_config:
                fact_template = field_config['prolog_fact']
                # Extract the predicate name and arguments
                predicate = fact_template.split('(')[0]
                args = fact_template.split('(')[1].split(')')[0].split(', ')
                person_var = args[0] if args else 'Person'
                
                if field_config.get('type') == 'boolean':
                    required_conditions.append(f"    {predicate}({person_var}, true)")
                elif field_config.get('type') == 'float':
                    required_conditions.append(f"    {predicate}({person_var}, Value), Value > 0")
                elif field_config.get('type') == 'date':
                    required_conditions.append(f"    {predicate}({person_var}, Date), Date =< '2019-02-01'")
                else:
                    required_conditions.append(f"    {predicate}({person_var}, _)")
        
        # Generate the main eligibility rule
        rules.append("% Core eligibility rule")
        rules.append("eligible_for_pmkisan(Person) :-")
        rules.extend(required_conditions)
        rules.append("    % Exclusion checks")
        rules.append("    not(excluded_from_pmkisan(Person)).")
        rules.append("")
        
        # Generate exclusion rules from YAML
        rules.extend(self._generate_exclusion_rules())
        
        return rules
    
    def _generate_exclusion_rules(self) -> List[str]:
        """Generate exclusion rules from YAML data model."""
        rules = []
        
        # Get employment fields for exclusions
        employment_fields = {k: v for k, v in self._get_all_fields().items() 
                           if v['section'] == 'employment'}
        
        if employment_fields:
            rules.append("% Exclusion rule")
            rules.append("excluded_from_pmkisan(Person) :-")
            
            # Government employees (except Group D/MTS)
            if 'employment_is_government_employee' in employment_fields:
                rules.append("    % Government employees (except Group D/MTS)")
                rules.append("    is_government_employee(Person, true),")
                rules.append("    government_post(Person, Post),")
                rules.append("    not(member(Post, ['Group D', 'MTS', 'Multi Tasking Staff'])),")
                rules.append("")
            
            # Income tax payers
            if 'employment_is_income_tax_payer' in employment_fields:
                rules.append("    % Income tax payers")
                rules.append("    is_income_tax_payer(Person, true),")
                rules.append("")
            
            # Professionals
            if 'employment_is_professional' in employment_fields:
                rules.append("    % Professionals")
                rules.append("    is_professional(Person, true),")
                rules.append("")
            
            # Pensioners with high pension
            if 'employment_is_pensioner' in employment_fields and 'employment_monthly_pension' in employment_fields:
                rules.append("    % Pensioners with high pension")
                rules.append("    is_pensioner(Person, true),")
                rules.append("    monthly_pension(Person, Pension),")
                rules.append("    Pension >= 10000,")
                rules.append("")
            
            # NRIs
            if 'employment_is_nri' in employment_fields:
                rules.append("    % NRIs")
                rules.append("    is_nri(Person, true).")
                rules.append("")
        
        return rules
    
    def _generate_helper_predicates(self) -> List[str]:
        """Generate helper predicates from YAML data model."""
        helpers = []
        
        # Family-related helpers
        family_fields = {k: v for k, v in self._get_all_fields().items() 
                        if v['section'] == 'family'}
        
        if family_fields:
            helpers.append("% Family-related helper predicates")
            
            # Check if person has husband
            helpers.append("% Check if person has husband")
            helpers.append("has_husband(Person) :-")
            helpers.append("    family_member(Person, 'husband', _, _).")
            helpers.append("")
            
            # Check if person has wife
            helpers.append("% Check if person has wife")
            helpers.append("has_wife(Person) :-")
            helpers.append("    family_member(Person, 'wife', _, _).")
            helpers.append("")
            
            # Check if person has minor children
            helpers.append("% Check if person has minor children")
            helpers.append("has_minor_children(Person) :-")
            helpers.append("    family_member_minor(Person, _, _, true).")
            helpers.append("")
            
            # Count family members
            helpers.append("% Count family members")
            helpers.append("family_size(Person, Size) :-")
            helpers.append("    findall(1, family_member(Person, _, _, _), Members),")
            helpers.append("    length(Members, Size).")
            helpers.append("")
            
            # Count dependents
            helpers.append("% Count dependents (minor family members)")
            helpers.append("dependents(Person, Count) :-")
            helpers.append("    findall(1, family_member_minor(Person, _, _, true), Dependents),")
            helpers.append("    length(Dependents, Count).")
            helpers.append("")
            
            # Check family structure
            helpers.append("% Check if family structure matches husband, wife, and minor children")
            helpers.append("is_husband_wife_minor_children(Person, true) :-")
            helpers.append("    has_husband(Person),")
            helpers.append("    has_wife(Person),")
            helpers.append("    has_minor_children(Person).")
            helpers.append("is_husband_wife_minor_children(Person, false) :-")
            helpers.append("    not(has_husband(Person));")
            helpers.append("    not(has_wife(Person));")
            helpers.append("    not(has_minor_children(Person)).")
            helpers.append("")
        
        # Land-related helpers
        land_fields = {k: v for k, v in self._get_all_fields().items() 
                      if v['section'] == 'land'}
        
        if 'land_land_ownership' in land_fields:
            helpers.append("% Check if person is a land owner")
            helpers.append("land_owner(Person, true) :-")
            helpers.append("    land_ownership(Person, 'owned').")
            helpers.append("land_owner(Person, false) :-")
            helpers.append("    land_ownership(Person, Type),")
            helpers.append("    Type \\= 'owned'.")
            helpers.append("")
        
        return helpers
    
    def _generate_special_provisions_rules(self) -> List[str]:
        """Generate special provisions rules from YAML."""
        rules = []
        
        special_fields = {k: v for k, v in self._get_all_fields().items() 
                         if v['section'] == 'special_provisions'}
        
        if special_fields:
            rules.append("% Special provisions rules")
            
            if 'special_provisions_region_special' in special_fields:
                rules.append("% Special provisions for North East states")
                rules.append("special_provision_northeast(Person) :-")
                rules.append("    region_special(Person, 'north_east'),")
                rules.append("    has_special_certificate(Person, true).")
                rules.append("")
                
                rules.append("% Special provisions for Manipur")
                rules.append("special_provision_manipur(Person) :-")
                rules.append("    region_special(Person, 'manipur'),")
                rules.append("    has_special_certificate(Person, true),")
                rules.append("    certificate_type(Person, 'village_authority').")
                rules.append("")
                
                rules.append("% Special provisions for Nagaland")
                rules.append("special_provision_nagaland(Person) :-")
                rules.append("    region_special(Person, 'nagaland'),")
                rules.append("    has_special_certificate(Person, true),")
                rules.append("    certificate_type(Person, 'village_council').")
                rules.append("")
                
                rules.append("% Special provisions for Jharkhand")
                rules.append("special_provision_jharkhand(Person) :-")
                rules.append("    region_special(Person, 'jharkhand'),")
                rules.append("    has_special_certificate(Person, true),")
                rules.append("    certificate_type(Person, 'vanshavali').")
                rules.append("")
        
        return rules
    
    def generate_prolog_file(self, output_file: str) -> str:
        """Generate complete Prolog file from enhanced canonical YAML."""
        prolog_content = [
            ":- encoding(utf8).",
            "",
            f"% {self._clean_string(self.scheme['name'])} Eligibility Rules - Generated from Enhanced Canonical YAML",
            f"% Scheme: {self._clean_string(self.scheme['name'])}",
            f"% Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"% Source: {self.yaml_file}",
            "",
            f"% Scheme Information",
            f"scheme_name('{self._clean_string(self.scheme['name'])}').",
            f"scheme_code('{self._clean_string(self.scheme['code'])}').",
            f"scheme_ministry('{self._clean_string(self.scheme['ministry'])}').",
            f"scheme_launched('{self._clean_string(self.scheme['launched_on'])}').",
            f"scheme_description('{self._clean_string(self.scheme['description'])}').",
            "",
            "% ============================================================================",
            "% DATA MODEL - ATOMIC FACTS",
            "% ============================================================================",
            "",
            "% This section defines all the atomic facts that can be extracted from farmer data.",
            "% Each fact represents a single piece of information about a farmer.",
            "",
            *self._generate_prolog_facts_from_yaml(),
            "",
            "% ============================================================================",
            "% ELIGIBILITY RULES",
            "% ============================================================================",
            "",
            *self._generate_eligibility_rules_from_yaml(),
            "",
            "% ============================================================================",
            "% SPECIAL PROVISIONS RULES",
            "% ============================================================================",
            "",
            *self._generate_special_provisions_rules(),
            "",
            "% ============================================================================",
            "% HELPER PREDICATES",
            "% ============================================================================",
            "",
            *self._generate_helper_predicates(),
            "",
            "% ============================================================================",
            "% END OF GENERATED PROLOG FILE",
            "% ============================================================================"
        ]
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(prolog_content))
        
        return output_file
    
    def _generate_pydantic_enums(self) -> List[str]:
        """Generate Pydantic enums from YAML data model."""
        enums = []
        
        # Add standard enums that are commonly used
        enums.append("class Relation(str, Enum):")
        enums.append('    HUSBAND = "husband"')
        enums.append('    WIFE = "wife"')
        enums.append('    SON = "son"')
        enums.append('    DAUGHTER = "daughter"')
        enums.append('    FATHER = "father"')
        enums.append('    MOTHER = "mother"')
        enums.append('    BROTHER = "brother"')
        enums.append('    SISTER = "sister"')
        enums.append('    OTHER = "other"')
        enums.append("")
        
        fields = self._get_all_fields()
        enum_fields = {k: v for k, v in fields.items() 
                      if v.get('type') == 'enum' and 'values' in v}
        
        for field_key, field_config in enum_fields.items():
            field_name = field_config['field']
            enum_name = ''.join(word.capitalize() for word in field_name.split('_'))
            values = field_config['values']
            
            enums.append(f"class {enum_name}(str, Enum):")
            for value in values:
                enum_key = value.upper().replace('-', '_').replace(' ', '_')
                enums.append(f'    {enum_key} = "{value}"')
            enums.append("")
        
        return enums
    
    def _generate_pydantic_models(self) -> List[str]:
        """Generate Pydantic models from YAML data model."""
        models = []
        
        # Group fields by section
        fields = self._get_all_fields()
        sections = {}
        
        for field_key, field_config in fields.items():
            section = field_config['section']
            if section not in sections:
                sections[section] = []
            sections[section].append((field_key, field_config))
        
        # Generate models for each section
        for section_name, section_fields in sections.items():
            if section_name == 'family':
                # Special handling for family members
                models.extend(self._generate_family_models())
            else:
                models.extend(self._generate_section_model(section_name, section_fields))
        
        return models
    
    def _generate_family_models(self) -> List[str]:
        """Generate family-related Pydantic models."""
        models = []
        
        models.append("@dataclass")
        models.append("class FamilyMember:")
        models.append('    """Family member information."""')
        models.append("    relation: Relation")
        models.append("    name: str")
        models.append("    age: int")
        models.append("    gender: Gender")
        models.append("    occupation: Optional[str] = None")
        models.append("    is_minor: bool = field(init=False)")
        models.append("")
        models.append("    def __post_init__(self):")
        models.append("        self.is_minor = self.age < 18")
        models.append("")
        
        return models
    
    def _generate_section_model(self, section_name: str, section_fields: List[tuple]) -> List[str]:
        """Generate Pydantic model for a section."""
        models = []
        
        # Convert section name to class name
        class_name = ''.join(word.capitalize() for word in section_name.split('_'))
        
        models.append("@dataclass")
        models.append(f"class {class_name}:")
        models.append(f'    """{section_name.replace("_", " ").title()} information."""')
        
        # Separate required and optional fields
        required_fields = []
        optional_fields = []
        
        for field_key, field_config in section_fields:
            field_name = field_config['field']
            field_type = self._get_pydantic_type(field_config)
            required = field_config.get('required', False)
            
            if required:
                required_fields.append((field_name, field_type))
            else:
                optional_fields.append((field_name, field_type))
        
        # Add required fields first
        for field_name, field_type in required_fields:
            models.append(f"    {field_name}: {field_type}")
        
        # Add optional fields with defaults
        for field_name, field_type in optional_fields:
            models.append(f"    {field_name}: Optional[{field_type}] = None")
        
        models.append("")
        
        return models
    
    def _get_pydantic_type(self, field_config: Dict[str, Any]) -> str:
        """Get Pydantic type for a field."""
        field_type = field_config.get('type', 'string')
        
        if field_type == 'string':
            return 'str'
        elif field_type == 'integer':
            return 'int'
        elif field_type == 'float':
            return 'float'
        elif field_type == 'boolean':
            return 'bool'
        elif field_type == 'date':
            return 'date'
        elif field_type == 'enum':
            field_name = field_config['field']
            enum_name = ''.join(word.capitalize() for word in field_name.split('_'))
            return enum_name
        elif field_type == 'list':
            return 'List[str]'
        elif field_type == 'list_of_objects':
            return 'List[Dict[str, Any]]'
        else:
            return 'str'
    
    def _generate_main_model(self) -> List[str]:
        """Generate the main farmer model."""
        models = []
        
        models.append("@dataclass")
        models.append(f"class {self._clean_string(self.scheme['name']).replace('-', '').replace(' ', '')}Farmer:")
        models.append(f'    """Complete {self._clean_string(self.scheme["name"])} farmer profile."""')
        
        # Add all section models as fields - all are optional with defaults
        fields = self._get_all_fields()
        sections = set(field_config['section'] for field_config in fields.values())
        
        for section in sections:
            if section == 'family':
                models.append("    family_members: List[FamilyMember] = field(default_factory=list)")
            else:
                class_name = ''.join(word.capitalize() for word in section.split('_'))
                models.append(f"    {section}: {class_name} = field(default_factory={class_name})")
        
        models.append("")
        
        # Add to_prolog_facts method
        models.append("    def to_prolog_facts(self) -> List[str]:")
        models.append('        """Convert farmer data to Prolog facts."""')
        models.append("        facts = []")
        models.append("        person = self.basic_info.farmer_id")
        models.append("")
        
        # Generate fact conversion for each field
        for field_key, field_config in fields.items():
            if 'prolog_fact' in field_config:
                fact_template = field_config['prolog_fact']
                section = field_config['section']
                field = field_config['field']
                
                if field_config.get('type') == 'boolean':
                    models.append(f"        # {section}.{field}")
                    models.append(f"        facts.append(f'{fact_template}')")
                elif field_config.get('type') == 'float':
                    models.append(f"        # {section}.{field}")
                    models.append(f"        facts.append(f'{fact_template}')")
                else:
                    models.append(f"        # {section}.{field}")
                    models.append(f"        if self.{section}.{field}:")
                    models.append(f"            facts.append(f'{fact_template}')")
                models.append("")
        
        models.append("        return facts")
        models.append("")
        
        return models
    
    def generate_pydantic_file(self, output_file: str) -> str:
        """Generate Pydantic data classes from YAML data model."""
        class_name = f"{self._clean_string(self.scheme['name']).replace('-', '').replace(' ', '')}Farmer"
        pydantic_content = [
            "#!/usr/bin/env python3",
            '"""',
            f"Pydantic data classes for {self._clean_string(self.scheme['name'])} scheme",
            f"Generated from enhanced canonical YAML",
            '"""',
            "",
            "from dataclasses import dataclass, field",
            "from typing import List, Optional, Dict, Any",
            "from datetime import date",
            "from enum import Enum",
            "from pydantic import BaseModel, Field",
            "",
            "",
            "# ============================================================================",
            "# ENUMS",
            "# ============================================================================",
            "",
            *self._generate_pydantic_enums(),
            "",
            "# ============================================================================",
            "# DATA MODELS",
            "# ============================================================================",
            "",
            *self._generate_pydantic_models(),
            "",
            "# ============================================================================",
            "# MAIN FARMER MODEL",
            "# ============================================================================",
            "",
            *self._generate_main_model(),
            "",
            "# ============================================================================",
            "# EXAMPLE USAGE",
            "# ============================================================================",
            "",
            "if __name__ == '__main__':",
            '    """Example usage."""',
            f"    # Create a sample farmer",
            f"    farmer = {class_name}(",
            "        basic_info=BasicInfo(",
            '            farmer_id="FARMER001",',
            '            name="Ram Kumar",',
            "            age=45,",
            "            gender=Gender.MALE,",
            '            phone_number="9876543210"',
            "        ),",
            "        location=Location(",
            '            state="Uttar Pradesh",',
            '            district="Lucknow",',
            '            sub_district_block="Block A",',
            '            village="Village A"',
            "        ),",
            "        land=Land(",
            "            land_size_acres=2.5,",
            "            land_ownership=LandOwnership.OWNED,",
            "            date_of_land_ownership=date(2018, 1, 1)",
            "        ),",
            "        financial=Financial(",
            "            bank_account=True,",
            '            account_number="1234567890",',
            '            ifsc_code="SBIN0001234"',
            "        ),",
            "        identity=Identity(",
            '            aadhaar_number="123456789012",',
            "            aadhaar_linked=True,",
            "            category=Category.GENERAL",
            "        )",
            "    )",
            "",
            "    # Generate Prolog facts",
            "    facts = farmer.to_prolog_facts()",
            '    print("Generated Prolog Facts:")',
            "    for fact in facts:",
            "        print(fact)",
        ]
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(pydantic_content))
        
        return output_file


def main():
    parser = argparse.ArgumentParser(description='Generate Prolog facts and Pydantic models from enhanced canonical YAML')
    parser.add_argument('yaml_file', help='Path to enhanced canonical YAML file')
    parser.add_argument('--output-dir', default='.', help='Output directory for generated files')
    parser.add_argument('--prolog-only', action='store_true', help='Generate only Prolog file')
    parser.add_argument('--pydantic-only', action='store_true', help='Generate only Pydantic file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.yaml_file):
        print(f"Error: YAML file '{args.yaml_file}' not found.")
        return 1
    
    generator = IntelligentPrologGenerator(args.yaml_file)
    
    # Generate output filenames
    base_name = os.path.splitext(os.path.basename(args.yaml_file))[0]
    prolog_file = os.path.join(args.output_dir, f"{base_name}_intelligent.pl")
    pydantic_file = os.path.join(args.output_dir, f"{base_name}_pydantic_models.py")
    
    try:
        if not args.pydantic_only:
            print(f"Generating intelligent Prolog file: {prolog_file}")
            generator.generate_prolog_file(prolog_file)
            print(f"✓ Prolog file generated successfully")
        
        if not args.prolog_only:
            print(f"Generating Pydantic models: {pydantic_file}")
            generator.generate_pydantic_file(pydantic_file)
            print(f"✓ Pydantic models generated successfully")
        
        print("\nGeneration completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error during generation: {e}")
        return 1


if __name__ == '__main__':
    exit(main()) 