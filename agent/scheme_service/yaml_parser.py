
import yaml
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

from ..models.scheme_models import (
    SchemeDefinition, SchemeMetadata, SchemeEligibility, SchemeBenefit,
    EligibilityRule, DataType, Operator
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YAMLSchemeParser:
    """
    Production-grade YAML parser for government scheme specifications.

    Features:
    - Flexible eligibility criteria parsing
    - Smart field type detection
    - Comprehensive error handling
    - Multiple scheme format support
    """

    def __init__(self):
        """Initialize the parser with field type mappings."""
        self.field_type_mapping = {
            # Demographics
            'age': DataType.NUMBER.value,
            'date_of_birth': DataType.DATE.value,
            'gender': DataType.STRING.value,
            'marital_status': DataType.STRING.value,
            'nationality': DataType.STRING.value,
            'citizenship': DataType.STRING.value,

            # Economic
            'income': DataType.NUMBER.value,
            'annual_income': DataType.NUMBER.value,
            'monthly_income': DataType.NUMBER.value,
            'family_income': DataType.NUMBER.value,
            'per_capita_income': DataType.NUMBER.value,

            # Agricultural
            'land_size': DataType.NUMBER.value,
            'land_area': DataType.NUMBER.value,
            'agricultural_land': DataType.NUMBER.value,
            'farm_size': DataType.NUMBER.value,
            'crop_type': DataType.STRING.value,

            # Employment
            'employment_status': DataType.STRING.value,
            'occupation': DataType.STRING.value,
            'job_category': DataType.STRING.value,
            'work_experience': DataType.NUMBER.value,

            # Social
            'caste': DataType.STRING.value,
            'religion': DataType.STRING.value,
            'disability_status': DataType.BOOLEAN.value,
            'education_level': DataType.STRING.value,

            # Family
            'family_size': DataType.NUMBER.value,
            'dependents': DataType.NUMBER.value,
            'children': DataType.NUMBER.value,

            # Location
            'state': DataType.STRING.value,
            'district': DataType.STRING.value,
            'village': DataType.STRING.value,
            'urban_rural': DataType.STRING.value,
            'location': DataType.STRING.value,

            # Status flags
            'is_farmer': DataType.BOOLEAN.value,
            'is_citizen': DataType.BOOLEAN.value,
            'is_bpl': DataType.BOOLEAN.value,
            'is_minority': DataType.BOOLEAN.value,
            'government_employee': DataType.BOOLEAN.value,
            'pension_recipient': DataType.BOOLEAN.value,
            'income_tax_payer': DataType.BOOLEAN.value,

            # Housing
            'house_type': DataType.STRING.value,
            'house_ownership': DataType.STRING.value,
            'construction_type': DataType.STRING.value,

            # Arrays/Lists
            'documents': DataType.ARRAY.value,
            'certificates': DataType.ARRAY.value,
            'qualifications': DataType.ARRAY.value
        }

        self.operator_patterns = [
            (r'(\w+)\s*(>=|≥)\s*([\d.]+)', '>='),
            (r'(\w+)\s*(<=|≤)\s*([\d.]+)', '<='),
            (r'(\w+)\s*(>)\s*([\d.]+)', '>'),
            (r'(\w+)\s*(<)\s*([\d.]+)', '<'),
            (r'(\w+)\s*(==|equals?|is)\s*([\w\s]+)', '=='),
            (r'(\w+)\s*(!=|not\s+equals?)\s*([\w\s]+)', '!='),
            (r'(\w+)\s*(in|belongs\s+to)\s*\[(.+?)\]', 'in'),
            (r'(\w+)\s*(not\s+in)\s*\[(.+?)\]', 'not_in'),
            (r'(\w+)\s*(between)\s*([\d.]+)\s*and\s*([\d.]+)', 'between'),
            (r'(\w+)\s*(contains)\s*"([^"]+)"', 'contains'),
            (r'(\w+)\s*(must\s+be|should\s+be)\s*(true|false)', '==')
        ]

    def parse_yaml_schemes(self, yaml_content: str) -> List[SchemeDefinition]:
        """
        Parse YAML content containing scheme definitions.

        Args:
            yaml_content: YAML content as string

        Returns:
            List of SchemeDefinition objects

        Raises:
            ValueError: If YAML is invalid or schemes cannot be parsed
        """
        try:
            logger.info("Parsing YAML scheme content")
            data = yaml.safe_load(yaml_content)

            schemes = []

            # Handle both single scheme and multiple schemes
            if 'schemes' in data:
                scheme_list = data['schemes']
            elif 'scheme' in data:
                scheme_list = [data['scheme']]
            else:
                # Assume the entire YAML is a single scheme
                scheme_list = [data]

            for scheme_data in scheme_list:
                try:
                    scheme_def = self._parse_single_scheme(scheme_data)
                    schemes.append(scheme_def)
                    logger.info(f"Successfully parsed scheme: {scheme_def.metadata.name}")
                except Exception as e:
                    logger.error(f"Error parsing scheme: {str(e)}")
                    continue

            if not schemes:
                raise ValueError("No valid schemes found in YAML content")

            logger.info(f"Successfully parsed {len(schemes)} scheme(s)")
            return schemes

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {str(e)}")
            raise ValueError(f"Invalid YAML format: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise ValueError(f"Error processing YAML content: {str(e)}")

    def _parse_single_scheme(self, scheme_data: Dict) -> SchemeDefinition:
        """
        Parse a single scheme from YAML data.

        Args:
            scheme_data: Dictionary containing scheme data

        Returns:
            SchemeDefinition object
        """
        # Parse metadata
        metadata = self._parse_metadata(scheme_data)

        # Parse eligibility criteria
        eligibility = self._parse_eligibility(scheme_data.get('eligibility', {}))

        # Parse benefits
        benefits = self._parse_benefits(scheme_data.get('benefits', []))

        # Parse documents
        documents = scheme_data.get('documents', [])
        if isinstance(documents, str):
            documents = [documents]

        # Parse application details
        application_data = scheme_data.get('application', {})
        application_modes = application_data.get('modes', [])
        if isinstance(application_modes, str):
            application_modes = [application_modes]

        # Parse monitoring
        monitoring = scheme_data.get('monitoring', {})

        # Parse notes
        notes = scheme_data.get('notes', '')

        return SchemeDefinition(
            metadata=metadata,
            eligibility=eligibility,
            benefits=benefits,
            documents=documents,
            application_modes=application_modes,
            monitoring=monitoring,
            notes=notes
        )

    def _parse_metadata(self, scheme_data: Dict) -> SchemeMetadata:
        """Parse scheme metadata from YAML data."""
        current_time = datetime.now().isoformat()

        return SchemeMetadata(
            scheme_id=scheme_data.get('id', ''),
            name=scheme_data.get('name', ''),
            code=scheme_data.get('code', ''),
            ministry=scheme_data.get('ministry', ''),
            launched_on=scheme_data.get('launched_on', ''),
            description=scheme_data.get('description', ''),
            category=scheme_data.get('metadata', {}).get('category'),
            disbursement=scheme_data.get('metadata', {}).get('disbursement'),
            version=scheme_data.get('version', '1.0.0'),
            created_date=scheme_data.get('created_date', current_time),
            modified_date=scheme_data.get('modified_date', current_time),
            status=scheme_data.get('status', 'active')
        )

    def _parse_eligibility(self, eligibility_data: Dict) -> SchemeEligibility:
        """Parse eligibility criteria from YAML data."""
        rules = []
        rule_counter = 1

        # Parse required criteria
        required_criteria = eligibility_data.get('required', [])
        if isinstance(required_criteria, str):
            required_criteria = [required_criteria]

        for criterion in required_criteria:
            rule = self._parse_criterion_to_rule(criterion, f"req_{rule_counter}")
            if rule:
                rules.append(rule)
                rule_counter += 1

        # Parse exclusion criteria
        exclusion_criteria = eligibility_data.get('exclusions', [])
        if isinstance(exclusion_criteria, str):
            exclusion_criteria = [exclusion_criteria]

        for criterion in exclusion_criteria:
            rule = self._parse_exclusion_to_rule(criterion, f"exc_{rule_counter}")
            if rule:
                rules.append(rule)
                rule_counter += 1

        # Parse direct rules if provided
        direct_rules = eligibility_data.get('rules', [])
        for rule_data in direct_rules:
            if isinstance(rule_data, dict):
                rule = EligibilityRule.from_dict(rule_data)
                rules.append(rule)
            rule_counter += 1

        logic = eligibility_data.get('logic', 'ALL')

        return SchemeEligibility(
            rules=rules,
            logic=logic,
            required_criteria=required_criteria,
            exclusion_criteria=exclusion_criteria
        )

    def _parse_criterion_to_rule(self, criterion: str, rule_id: str) -> Optional[EligibilityRule]:
        """
        Parse a criterion string into an eligibility rule.

        Args:
            criterion: Criterion string like "age >= 18"
            rule_id: Unique rule identifier

        Returns:
            EligibilityRule object or None if parsing fails
        """
        criterion = criterion.strip()

        for pattern, operator in self.operator_patterns:
            match = re.search(pattern, criterion, re.IGNORECASE)
            if match:
                field = match.group(1).lower().strip()

                # Determine data type
                data_type = self._detect_field_type(field, criterion)

                # Extract value(s)
                if operator == 'between':
                    value = [float(match.group(3)), float(match.group(4))]
                elif operator in ['in', 'not_in']:
                    items = match.group(3).split(',')
                    value = [item.strip().strip('"\'') for item in items]
                else:
                    value_str = match.group(3) if len(match.groups()) >= 3 else match.group(2)
                    value = self._convert_value(value_str, data_type)

                return EligibilityRule(
                    rule_id=rule_id,
                    field=field,
                    operator=operator,
                    value=value,
                    data_type=data_type,
                    description=criterion
                )

        # If no pattern matches, create a generic rule
        logger.warning(f"Could not parse criterion: {criterion}")
        return EligibilityRule(
            rule_id=rule_id,
            field="generic_requirement",
            operator="==",
            value=criterion,
            data_type=DataType.STRING.value,
            description=criterion
        )

    def _parse_exclusion_to_rule(self, exclusion: str, rule_id: str) -> Optional[EligibilityRule]:
        """Parse an exclusion criterion into an eligibility rule."""
        exclusion = exclusion.strip()

        # Convert exclusion to a positive rule with inverted logic
        for pattern, operator in self.operator_patterns:
            match = re.search(pattern, exclusion, re.IGNORECASE)
            if match:
                field = match.group(1).lower().strip()
                data_type = self._detect_field_type(field, exclusion)

                # Invert the operator for exclusion
                inverted_operator = self._invert_operator(operator)

                # Extract value
                if operator == 'between':
                    # For between exclusions, we need special handling
                    value = [float(match.group(3)), float(match.group(4))]
                    # Convert to "not between" logic using multiple rules or special operator
                    inverted_operator = 'not_between'
                elif operator in ['in', 'not_in']:
                    items = match.group(3).split(',')
                    value = [item.strip().strip('"\'') for item in items]
                else:
                    value_str = match.group(3) if len(match.groups()) >= 3 else match.group(2)
                    value = self._convert_value(value_str, data_type)

                return EligibilityRule(
                    rule_id=rule_id,
                    field=field,
                    operator=inverted_operator,
                    value=value,
                    data_type=data_type,
                    description=f"Exclusion: {exclusion}"
                )

        # Generic exclusion rule
        return EligibilityRule(
            rule_id=rule_id,
            field="generic_exclusion",
            operator="!=",
            value=exclusion,
            data_type=DataType.STRING.value,
            description=f"Exclusion: {exclusion}"
        )

    def _detect_field_type(self, field: str, context: str = "") -> str:
        """
        Detect the data type of a field based on field name and context.

        Args:
            field: Field name
            context: Context string for additional hints

        Returns:
            Data type string
        """
        # Direct mapping
        if field in self.field_type_mapping:
            return self.field_type_mapping[field]

        # Pattern-based detection
        if any(keyword in field for keyword in ['income', 'amount', 'size', 'area', 'age', 'count']):
            return DataType.NUMBER.value

        if any(keyword in field for keyword in ['is_', 'has_', 'can_', 'eligible']):
            return DataType.BOOLEAN.value

        if any(keyword in field for keyword in ['date', 'time', 'born', 'created']):
            return DataType.DATE.value

        if any(keyword in field for keyword in ['list', 'array', 'documents', 'certificates']):
            return DataType.ARRAY.value

        # Context-based detection
        if any(keyword in context.lower() for keyword in ['true', 'false', 'yes', 'no']):
            return DataType.BOOLEAN.value

        if re.search(r'\d+(\.\d+)?', context):
            return DataType.NUMBER.value

        # Default to string
        return DataType.STRING.value

    def _convert_value(self, value_str: str, data_type: str) -> Any:
        """Convert value string to appropriate Python type."""
        value_str = value_str.strip().strip('"\'')

        if data_type == DataType.NUMBER.value:
            try:
                if '.' in value_str:
                    return float(value_str)
                return int(value_str)
            except ValueError:
                logger.warning(f"Could not convert '{value_str}' to number, using 0")
                return 0

        elif data_type == DataType.BOOLEAN.value:
            return value_str.lower() in ['true', 'yes', '1', 'y', 't', 'on']

        elif data_type == DataType.ARRAY.value:
            if value_str.startswith('[') and value_str.endswith(']'):
                try:
                    return json.loads(value_str)
                except:
                    # Manual parsing
                    items = value_str[1:-1].split(',')
                    return [item.strip().strip('"\'') for item in items]
            return [value_str]

        return value_str

    def _invert_operator(self, operator: str) -> str:
        """Invert an operator for exclusion rules."""
        inversion_map = {
            '==': '!=',
            '!=': '==',
            '>': '<=',
            '>=': '<',
            '<': '>=',
            '<=': '>',
            'in': 'not_in',
            'not_in': 'in',
            'contains': 'not_contains',
            'not_contains': 'contains'
        }
        return inversion_map.get(operator, '!=')

    def _parse_benefits(self, benefits_data: List[Dict]) -> List[SchemeBenefit]:
        """Parse benefits from YAML data."""
        benefits = []

        if not benefits_data:
            return benefits

        for benefit_data in benefits_data:
            if isinstance(benefit_data, dict):
                benefit = SchemeBenefit(
                    type=benefit_data.get('type', 'Unknown'),
                    description=benefit_data.get('coverage_details', 
                                               benefit_data.get('description', 'No description')),
                    amount=benefit_data.get('total_amount') or benefit_data.get('amount_each'),
                    frequency=benefit_data.get('frequency', 'one-time'),
                    coverage_details=benefit_data.get('coverage_details')
                )
                benefits.append(benefit)
            elif isinstance(benefit_data, str):
                # Simple string benefit
                benefit = SchemeBenefit(
                    type='Benefit',
                    description=benefit_data
                )
                benefits.append(benefit)

        return benefits

    def convert_to_json_format(self, scheme_def: SchemeDefinition) -> Dict:
        """
        Convert YAML scheme definition to standardized JSON format.

        Args:
            scheme_def: SchemeDefinition object

        Returns:
            Dictionary in JSON schema format
        """
        return scheme_def.to_dict()

    def validate_parsed_scheme(self, scheme_def: SchemeDefinition) -> Tuple[bool, List[str]]:
        """
        Validate a parsed scheme definition.

        Args:
            scheme_def: SchemeDefinition to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Validate metadata
        if not scheme_def.metadata.scheme_id:
            errors.append("Scheme ID is required")

        if not scheme_def.metadata.name:
            errors.append("Scheme name is required")

        if not scheme_def.metadata.ministry:
            errors.append("Ministry is required")

        # Validate eligibility
        if not scheme_def.eligibility.rules:
            errors.append("At least one eligibility rule is required")

        # Validate benefits
        if not scheme_def.benefits:
            errors.append("At least one benefit must be specified")

        # Validate documents
        if not scheme_def.documents:
            errors.append("At least one required document must be specified")

        # Validate rules
        for rule in scheme_def.eligibility.rules:
            if not rule.field:
                errors.append(f"Rule {rule.rule_id}: field is required")

            if not rule.operator:
                errors.append(f"Rule {rule.rule_id}: operator is required")

            if rule.value is None:
                errors.append(f"Rule {rule.rule_id}: value is required")

        is_valid = len(errors) == 0
        return is_valid, errors
