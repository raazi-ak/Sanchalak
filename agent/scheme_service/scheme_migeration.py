# Create the YAML scheme migration utilities based on the provided scheme_spec.yaml

import yaml
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

class YAMLSchemeMigrator:
    """
    Migration utility to convert legacy scheme definitions into the new YAML format
    based on the provided scheme_spec.yaml structure.
    """
    
    def __init__(self):
        """Initialize the migrator with field mappings."""
        self.field_mappings = {
            # Common field mappings from legacy to new format
            'scheme_name': 'name',
            'scheme_id': 'id', 
            'scheme_code': 'code',
            'implementing_agency': 'ministry',
            'launch_date': 'launched_on',
            'scheme_description': 'description',
            'benefit_type': 'type',
            'benefit_amount': 'total_amount',
            'installment_amount': 'amount_each',
            'payment_frequency': 'frequency',
            'eligibility_criteria': 'required',
            'exclusion_criteria': 'exclusions',
            'required_documents': 'documents',
            'application_modes': 'modes'
        }
    
    def convert_legacy_to_yaml(self, legacy_scheme: Dict, scheme_type: str) -> str:
        """
        Convert legacy scheme format to YAML based on scheme_spec.yaml structure.
        
        Args:
            legacy_scheme: Legacy scheme data as dictionary
            scheme_type: Type of scheme for specific conversion logic
            
        Returns:
            YAML string in the new format
        """
        # Initialize the new scheme structure
        yaml_scheme = {
            'schemes': [self._build_scheme_structure(legacy_scheme, scheme_type)]
        }
        
        return yaml.dump(yaml_scheme, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    def _build_scheme_structure(self, legacy: Dict, scheme_type: str) -> Dict:
        """Build the complete scheme structure according to YAML spec."""
        
        scheme = {
            'id': self._get_mapped_value(legacy, 'scheme_id', f"{scheme_type.upper()}_001"),
            'name': self._get_mapped_value(legacy, 'scheme_name', ''),
            'code': self._get_mapped_value(legacy, 'scheme_code', ''),
            'ministry': self._get_mapped_value(legacy, 'implementing_agency', ''),
            'launched_on': self._get_mapped_value(legacy, 'launch_date', ''),
            'description': self._format_description(legacy.get('scheme_description', '')),
            'metadata': self._build_metadata(legacy),
            'eligibility': self._build_eligibility(legacy),
            'documents': self._build_documents(legacy),
            'application': self._build_application(legacy),
            'benefits': self._build_benefits(legacy),
            'monitoring': self._build_monitoring(legacy),
            'notes': self._format_notes(legacy.get('notes', ''))
        }
        
        return scheme
    
    def _get_mapped_value(self, legacy: Dict, field: str, default: str = '') -> str:
        """Get value using field mappings with fallback."""
        # Try direct field name
        if field in legacy:
            return str(legacy[field])
        
        # Try mapped field name
        mapped_field = self.field_mappings.get(field)
        if mapped_field and mapped_field in legacy:
            return str(legacy[mapped_field])
        
        # Try variations of the field name
        for key in legacy.keys():
            if key.lower() == field.lower() or key.lower() == mapped_field:
                return str(legacy[key])
        
        return default
    
    def _build_metadata(self, legacy: Dict) -> Dict:
        """Build metadata section."""
        metadata = {}
        
        # Map common metadata fields
        if 'category' in legacy:
            metadata['category'] = legacy['category']
        elif 'scheme_category' in legacy:
            metadata['category'] = legacy['scheme_category']
            
        if 'disbursement' in legacy:
            metadata['disbursement'] = legacy['disbursement']
        elif 'disbursement_method' in legacy:
            metadata['disbursement'] = legacy['disbursement_method']
        elif 'benefit_type' in legacy:
            metadata['disbursement'] = legacy['benefit_type']
            
        # Add any additional metadata fields
        for key, value in legacy.items():
            if key.startswith('metadata_') or key in ['target_group', 'sector', 'geographical_coverage']:
                clean_key = key.replace('metadata_', '')
                metadata[clean_key] = value
        
        return metadata
    
    def _build_eligibility(self, legacy: Dict) -> Dict:
        """Build eligibility section with required and exclusions."""
        eligibility = {
            'required': [],
            'exclusions': []
        }
        
        # Handle eligibility criteria
        if 'eligibility_criteria' in legacy:
            criteria = legacy['eligibility_criteria']
            if isinstance(criteria, list):
                for criterion in criteria:
                    if isinstance(criterion, dict):
                        rule_text = self._format_eligibility_rule(criterion)
                        eligibility['required'].append(rule_text)
                    else:
                        eligibility['required'].append(str(criterion))
            elif isinstance(criteria, str):
                eligibility['required'].append(criteria)
        
        # Handle legacy individual criteria fields
        age_criteria = self._extract_age_criteria(legacy)
        if age_criteria:
            eligibility['required'].append(age_criteria)
            
        income_criteria = self._extract_income_criteria(legacy)
        if income_criteria:
            eligibility['required'].append(income_criteria)
            
        land_criteria = self._extract_land_criteria(legacy)
        if land_criteria:
            eligibility['required'].append(land_criteria)
        
        # Handle exclusions
        if 'exclusion_criteria' in legacy:
            exclusions = legacy['exclusion_criteria']
            if isinstance(exclusions, list):
                eligibility['exclusions'].extend(exclusions)
            elif isinstance(exclusions, str):
                eligibility['exclusions'].append(exclusions)
        
        # Add common exclusions
        if legacy.get('exclude_government_employees', False):
            eligibility['exclusions'].append('government_employee == true')
        if legacy.get('exclude_income_tax_payers', False):
            eligibility['exclusions'].append('income_tax_payer == true')
        
        return eligibility
    
    def _format_eligibility_rule(self, criterion: Dict) -> str:
        """Format a criterion dictionary into rule text."""
        field = criterion.get('field', '')
        operator = criterion.get('operator', '==')
        value = criterion.get('value', '')
        
        return f"{field} {operator} {value}"
    
    def _extract_age_criteria(self, legacy: Dict) -> Optional[str]:
        """Extract age-related criteria."""
        if 'min_age' in legacy:
            return f"age >= {legacy['min_age']}"
        elif 'age_limit' in legacy:
            return f"age <= {legacy['age_limit']}"
        elif 'age_range' in legacy:
            age_range = legacy['age_range']
            if isinstance(age_range, dict):
                min_age = age_range.get('min', 18)
                max_age = age_range.get('max', 65)
                return f"age between {min_age} and {max_age}"
        return None
    
    def _extract_income_criteria(self, legacy: Dict) -> Optional[str]:
        """Extract income-related criteria."""
        if 'max_income' in legacy:
            return f"annual_income <= {legacy['max_income']}"
        elif 'income_limit' in legacy:
            return f"annual_income < {legacy['income_limit']}"
        elif 'annual_income' in legacy:
            income_data = legacy['annual_income']
            if isinstance(income_data, dict):
                if 'max' in income_data:
                    return f"annual_income <= {income_data['max']}"
        return None
    
    def _extract_land_criteria(self, legacy: Dict) -> Optional[str]:
        """Extract land-related criteria."""
        if 'min_land_size' in legacy:
            return f"land_size >= {legacy['min_land_size']}"
        elif 'land_holding' in legacy:
            land_data = legacy['land_holding']
            if isinstance(land_data, dict):
                if 'min' in land_data:
                    return f"land_size >= {land_data['min']}"
            else:
                return f"land_size > 0"
        return None
    
    def _build_documents(self, legacy: Dict) -> List[str]:
        """Build documents list."""
        documents = []
        
        if 'required_documents' in legacy:
            docs = legacy['required_documents']
            if isinstance(docs, list):
                documents.extend([str(doc) for doc in docs])
            elif isinstance(docs, str):
                documents.append(docs)
        
        # Add documents from other fields
        for field in ['documents', 'documentation', 'papers_required']:
            if field in legacy:
                docs = legacy[field]
                if isinstance(docs, list):
                    documents.extend([str(doc) for doc in docs])
                elif isinstance(docs, str):
                    documents.append(docs)
        
        return list(set(documents))  # Remove duplicates
    
    def _build_application(self, legacy: Dict) -> Dict:
        """Build application section."""
        application = {
            'modes': [],
            'timelines': {},
            'status_lookup_params': []
        }
        
        # Application modes
        if 'application_modes' in legacy:
            modes = legacy['application_modes']
            if isinstance(modes, list):
                application['modes'] = modes
            elif isinstance(modes, str):
                application['modes'] = [modes]
        else:
            # Default modes
            application['modes'] = ['Online', 'Offline']
        
        # Timelines
        if 'application_deadline' in legacy:
            application['timelines']['application_deadline'] = legacy['application_deadline']
        if 'processing_time' in legacy:
            application['timelines']['processing_time'] = legacy['processing_time']
        
        # Status lookup parameters
        if 'status_lookup_params' in legacy:
            params = legacy['status_lookup_params']
            if isinstance(params, list):
                application['status_lookup_params'] = params
            else:
                application['status_lookup_params'] = [str(params)]
        else:
            application['status_lookup_params'] = ['application_id', 'aadhaar_number']
        
        return application
    
    def _build_benefits(self, legacy: Dict) -> List[Dict]:
        """Build benefits list."""
        benefits = []
        
        if 'benefits' in legacy and isinstance(legacy['benefits'], list):
            # If benefits already in list format
            for benefit in legacy['benefits']:
                if isinstance(benefit, dict):
                    benefits.append(benefit)
                else:
                    benefits.append({'type': str(benefit), 'coverage_details': str(benefit)})
        else:
            # Build benefit from individual fields
            benefit = {}
            
            if 'benefit_type' in legacy:
                benefit['type'] = legacy['benefit_type']
            
            if 'benefit_amount' in legacy:
                benefit['total_amount'] = legacy['benefit_amount']
            elif 'amount' in legacy:
                benefit['total_amount'] = legacy['amount']
            
            if 'installment_amount' in legacy:
                benefit['amount_each'] = legacy['installment_amount']
            
            if 'frequency' in legacy:
                benefit['frequency'] = legacy['frequency']
            elif 'payment_frequency' in legacy:
                benefit['frequency'] = legacy['payment_frequency']
            
            if 'benefit_description' in legacy:
                benefit['coverage_details'] = legacy['benefit_description']
            
            if benefit:  # Only add if we have some benefit data
                benefits.append(benefit)
        
        return benefits if benefits else [{'type': 'Government Benefit', 'coverage_details': 'Details to be specified'}]
    
    def _build_monitoring(self, legacy: Dict) -> Dict:
        """Build monitoring section."""
        monitoring = {}
        
        if 'monitoring' in legacy:
            monitoring.update(legacy['monitoring'])
        
        # Add specific monitoring fields if available
        if 'claim_settlement_target' in legacy:
            monitoring['claim_settlement_target'] = legacy['claim_settlement_target']
        
        if 'participating_entities' in legacy:
            monitoring['participating_entities'] = legacy['participating_entities']
        
        if 'instalment_tracking' in legacy:
            monitoring['instalment_tracking'] = legacy['instalment_tracking']
        
        return monitoring
    
    def _format_description(self, description: str) -> str:
        """Format description using YAML literal style."""
        if not description:
            return ""
        
        # Clean up description text
        description = description.strip()
        if len(description) > 80:  # Use literal style for long descriptions
            return description
        return description
    
    def _format_notes(self, notes: str) -> str:
        """Format notes using YAML literal style."""
        if not notes:
            return ""
        return notes.strip()

# Create migrator instance
migrator = YAMLSchemeMigrator()
print("YAML Scheme Migrator created successfully!")
print("Ready to convert legacy schemes to the new YAML format.")