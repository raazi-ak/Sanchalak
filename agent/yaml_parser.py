# yaml_parser.py

import yaml
from datetime import datetime
from typing import List, Dict
import re

class SchemeMetadata:
    def __init__(self, id, name, code, ministry, launched_on, description, category=None, disbursement=None):
        self.id = id
        self.name = name
        self.code = code
        self.ministry = ministry
        self.launched_on = launched_on
        self.description = description
        self.category = category
        self.disbursement = disbursement

class SchemeDefinition:
    def __init__(self, metadata, eligibility_required, eligibility_exclusions, documents, application_modes, benefits, monitoring=None, notes=None):
        self.metadata = metadata
        self.eligibility_required = eligibility_required
        self.eligibility_exclusions = eligibility_exclusions
        self.documents = documents
        self.application_modes = application_modes
        self.benefits = benefits
        self.monitoring = monitoring
        self.notes = notes

class YAMLSchemeParser:
    def parse_yaml(self, yaml_str: str) -> List[SchemeDefinition]:
        data = yaml.safe_load(yaml_str)
        schemes = []
        for scheme in data.get('schemes', []):
            metadata = SchemeMetadata(
                id=scheme.get('id', ''),
                name=scheme.get('name', ''),
                code=scheme.get('code', ''),
                ministry=scheme.get('ministry', ''),
                launched_on=scheme.get('launched_on', ''),
                description=scheme.get('description', ''),
                category=scheme.get('metadata', {}).get('category'),
                disbursement=scheme.get('metadata', {}).get('disbursement')
            )
            eligibility_required = scheme.get('eligibility', {}).get('required', [])
            eligibility_exclusions = scheme.get('eligibility', {}).get('exclusions', [])
            documents = scheme.get('documents', [])
            application_modes = scheme.get('application', {}).get('modes', [])
            benefits = scheme.get('benefits', [])
            monitoring = scheme.get('monitoring', {})
            notes = scheme.get('notes', '')
            schemes.append(SchemeDefinition(metadata, eligibility_required, eligibility_exclusions, documents, application_modes, benefits, monitoring, notes))
        return schemes

    def convert_to_json_schema(self, scheme: SchemeDefinition) -> Dict:
        rules = []
        for idx, req in enumerate(scheme.eligibility_required):
            rule = self._parse_requirement(req, f"req_{idx+1}")
            if rule:
                rules.append(rule)
        for idx, excl in enumerate(scheme.eligibility_exclusions):
            rule = self._parse_requirement(excl, f"exc_{idx+1}", exclude=True)
            if rule:
                rules.append(rule)
        return {
            "metadata": {
                "scheme_id": scheme.metadata.id,
                "name": scheme.metadata.name,
                "description": scheme.metadata.description,
                "agency": scheme.metadata.ministry,
                "code": scheme.metadata.code,
                "launched_on": scheme.metadata.launched_on,
                "version": "1.0.0",
                "created_date": datetime.now().isoformat(),
                "modified_date": datetime.now().isoformat(),
                "status": "active"
            },
            "benefits": self._convert_benefits(scheme.benefits),
            "eligibility": {
                "rules": rules,
                "logic": "ALL"
            },
            "documentation": self._convert_documents(scheme.documents),
            "application_process": {
                "modes": scheme.application_modes,
                "steps": []
            },
            "monitoring": scheme.monitoring,
            "notes": scheme.notes
        }

    def _parse_requirement(self, req_str: str, rule_id: str, exclude=False):
        # Basic pattern matching
        pattern = r'(\w+)\s*(>=|<=|>|<|==|!=|in|not_in|between|contains|not_contains|starts_with|ends_with)?\s*(.*)'
        match = re.match(pattern, req_str)
        if not match:
            return None
        field, operator, value_str = match.groups()
        operator = operator or "=="
        data_type = self._infer_type(field)
        value = self._parse_value(value_str.strip(), data_type)
        if exclude:
            operator = self._invert_operator(operator)
        return {
            "rule_id": rule_id,
            "field": field,
            "operator": operator,
            "value": value,
            "data_type": data_type,
            "description": req_str
        }

    def _parse_value(self, val_str, dtype):
        if dtype == "number":
            try:
                return float(val_str)
            except:
                return 0
        elif dtype == "boolean":
            return val_str.lower() in ["true", "yes", "1"]
        elif dtype == "string":
            return val_str.strip('"\'')
        elif dtype == "array":
            # parse list
            if val_str.startswith('[') and val_str.endswith(']'):
                items = val_str[1:-1].split(',')
                return [item.strip().strip('"\'') for item in items]
            return [val_str]
        elif dtype == "date":
            return val_str
        else:
            return val_str

    def _infer_type(self, field):
        # Basic inference, can be extended
        if "age" in field or "income" in field or "size" in field:
            return "number"
        if "date" in field or "on" in field:
            return "date"
        if "is_" in field or "status" in field:
            return "boolean"
        return "string"

    def _invert_operator(self, op):
        mapping = {
            "==": "!=",
            "!=": "==",
            ">": "<=",
            "<": ">=",
            ">=": "<",
            "<=": ">",
            "in": "not_in",
            "not_in": "in",
            "between": "not_between",
            "contains": "not_contains",
            "not_contains": "contains",
            "starts_with": "not_starts_with",
            "ends_with": "not_ends_with"
        }
        return mapping.get(op, "!=")

    def _convert_benefits(self, benefits):
        if not benefits:
            return {}
        primary = benefits[0]
        return {
            "type": primary.get("type", "Financial Assistance"),
            "amount": primary.get("total_amount") or primary.get("amount_each"),
            "description": primary.get("coverage_details", ""),
            "frequency": primary.get("frequency", "one-time")
        }

    def _convert_documents(self, docs):
        return [{"document_type": d, "required": True, "description": f"Required: {d}"} for d in docs]
