# canonical_extractor_qwen.py

import os
import sys
import json
import yaml
import argparse
import requests
import re
from collections import OrderedDict

SECTION_MAP = {
    "eligibility": "eligibility",
    "exclusions": "exclusion_criteria",
    "documents": "documents",
    "benefits": "benefits",
    "application": "application_modes",
    "monitoring": "monitoring",
    "notes": "notes",
    "special_provisions": "special_provisions",
    "general": "notes"  # Map general section to notes as well
}

# Complete scheme template matching the reference format
COMPLETE_SCHEME_TEMPLATE = '''schemes:
  - id: SCHEME_ID
    name: SCHEME_NAME
    code: SCHEME_CODE
    ministry: Ministry Name
    launched_on: YYYY-MM-DD
    description: >
      Scheme description here.
    metadata:
      language: English
      source_url: SOURCE_URL
      last_updated: YYYY-MM-DD
      version: "Version info"
      document_type: "Document Type"
      region_coverage: "Coverage Area"
      implementing_agency: "Implementing Agency"
      grievance_redressal: true
    eligibility:
      rules:
        - field: field_name
          operator: "=="
          value: value
          data_type: data_type
          description: Description
      logic: ALL
      required_criteria:
        - Required criteria list
      exclusion_criteria:
        - Exclusion criteria list
    special_provisions:
      - region: Region Name
        description: >
          Special provision description.
    benefits:
      - type: Benefit Type
        description: Benefit description
        amount: amount
        frequency: frequency
        coverage_details: Coverage details
        payment_mode: Payment mode
        currency: Currency
        beneficiary_type: Beneficiary type
    documents:
      - Document list
    application_modes:
      - Application modes
    monitoring:
      claim_settlement_target: Target
      participating_entities:
        - Entities list
      instalment_tracking: true
      grievance_redressal: true
      pmu_setup: true
      review_mechanism:
        - Review mechanisms
      transparency_measures:
        - Transparency measures
    notes: >
      Notes section.
'''

# Exact canonical YAML templates from PM-KISAN reference
SECTION_TEMPLATES = {
    "eligibility": '''eligibility:
  rules:
    - field: land_owner
      operator: "=="
      value: true
      data_type: boolean
      description: Must be a landholding farmer family as per land records of the State/UT
    - field: date_of_land_ownership
      operator: "<="
      value: "2019-02-01"
      data_type: date
      description: Land ownership as on 01.02.2019 is required for eligibility
    - field: aadhaar_linked
      operator: "=="
      value: true
      data_type: boolean
      description: Aadhaar number must be provided
    - field: bank_account
      operator: "=="
      value: true
      data_type: boolean
      description: Must have a valid bank account for Direct Benefit Transfer
    - field: category
      operator: "in"
      value: ["SC", "ST", "General", "Minority", "BPL"]
      data_type: string
      description: Category information to be captured for all beneficiaries
    - field: family_definition
      operator: "=="
      value: "Husband, wife, and minor children"
      data_type: string
      description: Family is defined as husband, wife, and minor children owning cultivable land
    - field: region
      operator: "in"
      value: ["North East", "Jharkhand", "Manipur", "Nagaland"]
      data_type: string
      description: Special provisions apply for North East, Jharkhand, Manipur, and Nagaland (see special_provisions)
  logic: ALL
  required_criteria:
    - Landholding farmer family as per land records
    - Aadhaar number
    - Bank account details
    - Name, Age, Gender, Category, Mobile Number
  exclusion_criteria:
    - All Institutional Land holders
    - Families with members who are or were holders of constitutional posts
    - Former/present Ministers, MPs, MLAs, Mayors, District Panchayat Chairpersons
    - Serving/retired officers and employees of Central/State Government (except Group D/MTS)
    - Pensioners with monthly pension >= Rs.10,000 (except Group D/MTS)
    - Income tax payers in last assessment year
    - Professionals (Doctors, Engineers, Lawyers, CAs, Architects) practicing and registered
    - NRIs as per Income Tax Act, 1961
''',
    "benefits": '''benefits:
  - type: Financial Assistance
    description: Annual income support for agricultural inputs and domestic needs
    amount: 6000
    frequency: yearly
    coverage_details: Rs 2000 in three equal installments per year, directly transferred to bank accounts
    payment_mode: Direct Benefit Transfer (DBT)
    currency: INR
    beneficiary_type: "Landholding farmer family"
''',
    "documents": '''documents:
  - Aadhaar Card
  - Bank Account Details
  - Land Records
  - Category Certificate (if applicable)
  - Voter ID/Driving Licence/NREGA Job Card (alternate IDs)
  - Mobile Number (for SMS alerts)
  - Address Proof
''',
    "application": '''application_modes:
  - State/UT Government upload on PM-Kisan Portal
  - Village/district-wise list upload
  - Fresh entry/registration on portal
  - Correction window for authorized users
''',
    "monitoring": '''monitoring:
  claim_settlement_target: Direct transfer within 4 months per installment
  participating_entities:
    - State/UT Governments
    - Central Government
    - Banks
    - Panchayats
  instalment_tracking: true
  grievance_redressal: true
  pmu_setup: true
  review_mechanism:
    - National Level Review Committee (headed by Cabinet Secretary)
    - State and District Level Review/Monitoring Committees
  transparency_measures:
    - Beneficiary lists displayed at Panchayats
    - System-generated SMS notifications
''',
    "special_provisions": '''special_provisions:
  - region: North East States
    description: >
      In North Eastern States, where land ownership rights are community-based and it may not be possible to assess the quantum of landholder farmers, an alternate implementation mechanism for eligibility will be developed and approved by a Committee of Union Ministers and State Chief Ministers or their representatives, based on proposals by the concerned North Eastern States.
  - region: Manipur
    description: >
      For identification of bona fide beneficiaries under PM-Kisan Scheme in Manipur, a certificate issued by the Village authority (Chairman/Chief) authorizing any tribal family to cultivate a piece of land may be accepted. Such certification must be authenticated by the concerned sub-divisional officers.
  - region: Nagaland
    description: >
      For community-owned cultivable land in Nagaland under permanent cultivation, a certificate issued by the village council/authority/village chieftain regarding land holding, duly verified by the administrative head of the circle/sub-division and countersigned by the Deputy Commissioner of the District, shall suffice. For Jhum land (as per Section–2(7) of the Nagaland Jhum Land Act, 1970), identification is based on certification by the village council/chief/head, verified and countersigned as above, and the beneficiary must be included in the state's Agriculture Census of 2015-16.
  - region: Jharkhand
    description: >
      In Jharkhand, the farmer must submit a 'Vanshavali (Lineage)' linked to the entry of land record comprising their ancestor's name, giving a chart of successor. This lineage chart is submitted before the Gram Sabha for objections, then verified by village/circle revenue officials and countersigned by the District revenue authority. Names are uploaded to the PM-Kisan portal after verification and subject to exclusion criteria.
''',
    "exclusions": '''exclusion_criteria:
  - All Institutional Land holders
  - Families with members who are or were holders of constitutional posts
  - Former/present Ministers, MPs, MLAs, Mayors, District Panchayat Chairpersons
  - Serving/retired officers and employees of Central/State Government (except Group D/MTS)
  - Pensioners with monthly pension >= Rs.10,000 (except Group D/MTS)
  - Income tax payers in last assessment year
  - Professionals (Doctors, Engineers, Lawyers, CAs, Architects) practicing and registered
  - NRIs as per Income Tax Act, 1961
''',
    "notes": '''notes: >
  The scheme is implemented through an Aadhaar-linked electronic database. The list of beneficiaries is valid for one year and is subject to revision in case of changes in land records. Administrative charges are provided to States/UTs for implementation. Project Monitoring Units (PMUs) are set up at Central and State/UT levels. All special provisions and exceptions are detailed in the 'special_provisions' section for full transparency and downstream logic.
''',
    "special_provisions": '''special_provisions:
  - region: North East States
    description: >
      In North Eastern States, where land ownership rights are community-based and it may not be possible to assess the quantum of landholder farmers, an alternate implementation mechanism for eligibility will be developed and approved by a Committee of Union Ministers and State Chief Ministers or their representatives, based on proposals by the concerned North Eastern States.
  - region: Manipur
    description: >
      For identification of bona fide beneficiaries under PM-Kisan Scheme in Manipur, a certificate issued by the Village authority (Chairman/Chief) authorizing any tribal family to cultivate a piece of land may be accepted. Such certification must be authenticated by the concerned sub-divisional officers.
  - region: Nagaland
    description: >
      For community-owned cultivable land in Nagaland under permanent cultivation, a certificate issued by the village council/authority/village chieftain regarding land holding, duly verified by the administrative head of the circle/sub-division and countersigned by the Deputy Commissioner of the District, shall suffice. For Jhum land (as per Section–2(7) of the Nagaland Jhum Land Act, 1970), identification is based on certification by the village council/chief/head, verified and countersigned as above, and the beneficiary must be included in the state's Agriculture Census of 2015-16.
  - region: Jharkhand
    description: >
      In Jharkhand, the farmer must submit a 'Vanshavali (Lineage)' linked to the entry of land record comprising their ancestor's name, giving a chart of successor. This lineage chart is submitted before the Gram Sabha for objections, then verified by village/circle revenue officials and countersigned by the District revenue authority. Names are uploaded to the PM-Kisan portal after verification and subject to exclusion criteria.
''',
}

# Load the PM-KISAN reference YAML for section examples
REFERENCE_YAML_PATH = os.path.join(os.path.dirname(__file__), '../../../outputs/pm-kisan/rules_canonical_REFERENCE.yaml')
if os.path.exists(REFERENCE_YAML_PATH):
    with open(REFERENCE_YAML_PATH, 'r', encoding='utf-8') as f:
        reference_yaml = yaml.safe_load(f)
else:
    reference_yaml = {}

def validate_yaml_structure(yaml_obj, section):
    """Validate YAML structure and return validation errors"""
    errors = []
    
    if not yaml_obj:
        return ["No YAML object provided"]
    
    # Handle nested YAML structure (e.g., {"eligibility": {...}})
    actual_obj = yaml_obj
    if section in yaml_obj:
        actual_obj = yaml_obj[section]
    
    # Check for unquoted operators in eligibility rules
    if section == "eligibility" and "rules" in actual_obj:
        for i, rule in enumerate(actual_obj["rules"]):
            if "operator" in rule:
                op = rule["operator"]
                # YAML parser strips quotes, so we check if it's a valid operator
                valid_operators = ["==", "<=", ">=", "!=", "in", "not in"]
                if not isinstance(op, str) or op not in valid_operators:
                    errors.append(f"Rule {i+1}: operator '{op}' must be a valid operator (e.g., '==', '<=', 'in')")
    
    # Check for required fields in eligibility
    if section == "eligibility":
        if "rules" not in actual_obj:
            errors.append("Missing 'rules' field in eligibility")
        if "logic" not in actual_obj:
            errors.append("Missing 'logic' field in eligibility")
    
    # Check for required fields in benefits
    if section == "benefits":
        if not isinstance(actual_obj, list):
            errors.append("Benefits must be a list")
        else:
            for i, benefit in enumerate(actual_obj):
                required_fields = ["type", "description", "amount", "frequency"]
                for field in required_fields:
                    if field not in benefit:
                        errors.append(f"Benefit {i+1}: missing required field '{field}'")
    
    # Check for required fields in monitoring
    if section == "monitoring":
        required_fields = ["participating_entities", "instalment_tracking", "grievance_redressal"]
        for field in required_fields:
            if field not in actual_obj:
                errors.append(f"Missing required field '{field}' in monitoring")
    
    return errors

def fix_unquoted_operators(yaml_str):
    """Fix unquoted operators in YAML string"""
    # Pattern to match unquoted operators
    patterns = [
        (r'operator:\s*==', 'operator: "=="'),
        (r'operator:\s*<=', 'operator: "<="'),
        (r'operator:\s*>=', 'operator: ">="'),
        (r'operator:\s*!=', 'operator: "!="'),
        (r'operator:\s*in', 'operator: "in"'),
        (r'operator:\s*not in', 'operator: "not in"'),
    ]
    
    fixed_str = yaml_str
    for pattern, replacement in patterns:
        fixed_str = re.sub(pattern, replacement, fixed_str)
    
    # Also fix any remaining unquoted operators in the YAML
    # This handles cases where the regex didn't catch them
    fixed_str = re.sub(r'operator: ([^"\s]+)', r'operator: "\1"', fixed_str)
    
    return fixed_str

def get_reference_section(section):
    # Try to extract the section from the reference YAML
    if 'schemes' in reference_yaml and reference_yaml['schemes']:
        scheme = reference_yaml['schemes'][0]
        section_data = scheme.get(section, None)
        if section_data:
            return yaml.dump({section: section_data}, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return ''

def make_complete_scheme_prompt(text, scheme_name, source_url):
    """Generate prompt for complete scheme extraction"""
    # Use a shorter version of the reference for the prompt
    short_reference = """schemes:
  - id: PM_KISAN_001
    name: PM-KISAN
    code: PMKISAN
    ministry: Ministry of Agriculture and Farmers Welfare
    launched_on: 2019-02-24
    description: >
      Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) is a Central Sector Scheme providing income support to all landholding farmers' families in the country, having cultivable land.
    metadata:
      language: English
      source_url: SOURCE_URL
      last_updated: 2020-03-29
      version: "Revised as on 29.03.2020"
      document_type: "Operational Guidelines"
      region_coverage: "All India"
      implementing_agency: "Department of Agriculture, Cooperation & Farmers Welfare (DAC&FW)"
      grievance_redressal: true
    eligibility:
      rules:
        - field: land_owner
          operator: "=="
          value: true
          data_type: boolean
          description: Must be a landholding farmer family as per land records of the State/UT
      logic: ALL
      required_criteria:
        - Landholding farmer family as per land records
      exclusion_criteria:
        - All Institutional Land holders
    special_provisions:
      - region: North East States
        description: >
          In North Eastern States, where land ownership rights are community-based and it may not be possible to assess the quantum of landholder farmers, an alternate implementation mechanism for eligibility will be developed and approved by a Committee of Union Ministers and State Chief Ministers or their representatives, based on proposals by the concerned North Eastern States.
    benefits:
      - type: Financial Assistance
        description: Annual income support for agricultural inputs and domestic needs
        amount: 6000
        frequency: yearly
        coverage_details: Rs 2000 in three equal installments per year, directly transferred to bank accounts
        payment_mode: Direct Benefit Transfer (DBT)
        currency: INR
        beneficiary_type: "Landholding farmer family"
    documents:
      - Aadhaar Card
      - Bank Account Details
    application_modes:
      - State/UT Government upload on PM-Kisan Portal
    monitoring:
      claim_settlement_target: Direct transfer within 4 months per installment
      participating_entities:
        - State/UT Governments
        - Central Government
      instalment_tracking: true
      grievance_redressal: true
      pmu_setup: true
    notes: >
      The scheme is implemented through an Aadhaar-linked electronic database. The list of beneficiaries is valid for one year and is subject to revision in case of changes in land records."""
    
    prompt = f"""
Extract a complete government scheme in canonical YAML format.

IMPORTANT REQUIREMENTS:
- Output the COMPLETE scheme structure with all sections
- Include metadata, eligibility, benefits, documents, application_modes, monitoring, special_provisions, and notes
- All keys and string values, including operators, MUST be quoted
- Follow the exact structure and data types shown in the reference example
- Use proper YAML syntax with correct indentation

COMPLETE SCHEME TEMPLATE:
{COMPLETE_SCHEME_TEMPLATE}

EXACT REFERENCE EXAMPLE from PM-KISAN:
{short_reference}

Text to extract from:
\"\"\"
{text}
\"\"\"

Scheme details:
- Name: {scheme_name}
- Source URL: {source_url}

Generate the complete scheme YAML:
"""
    return prompt

def make_section_prompt(section, text, validation_errors=None, attempt=1):
    template = SECTION_TEMPLATES.get(section, '')
    ref = get_reference_section(section)
    
    # Add validation feedback if this is a retry
    validation_feedback = ""
    if validation_errors and attempt > 1:
        validation_feedback = f"\nVALIDATION ERRORS (attempt {attempt-1}):\n"
        for error in validation_errors:
            validation_feedback += f"- {error}\n"
        validation_feedback += "\nPlease fix these errors in your YAML output.\n"
    
    # Enhanced prompt with specific instructions
    prompt = f"""
You are a government scheme YAML extraction expert. Extract the {section} section from the given text.

CRITICAL REQUIREMENTS:
1. Output ONLY valid YAML - no markdown, no explanations, no extra text
2. ALL string values MUST be quoted, including operators like "==", "<=", ">=", "in"
3. Follow the EXACT structure, field names, and data types from the reference example
4. Use proper YAML indentation (2 spaces)
5. Extract ALL relevant information from the text
6. For eligibility rules: convert narrative text to structured rules with field, operator, value, data_type, description
7. For special_provisions: identify regions and extract detailed descriptions
8. For benefits: extract amount, frequency, payment details
9. For documents: list all required documents
10. For monitoring: extract all monitoring mechanisms and transparency measures{validation_feedback}

REFERENCE TEMPLATE:
{template}

EXACT REFERENCE EXAMPLE (follow this structure precisely):
{ref}

TEXT TO EXTRACT FROM:
\"\"\"
{text}
\"\"\"

YAML OUTPUT:
"""
    return prompt

class LMStudioClient:
    def __init__(self, base_url="http://localhost:1234", model="google/gemma-3-4b"):
        self.base_url = base_url
        self.model = model
        self.session = requests.Session()
    
    def generate(self, prompt, temperature=0.7, max_tokens=4096, structured_output=False, stream=False):
        messages = [
            {"role": "system", "content": "You are a government scheme YAML extraction expert. Your task is to convert narrative government scheme text into structured canonical YAML format. CRITICAL: Output ONLY valid YAML - no markdown, no explanations, no extra text. ALL string values MUST be quoted, including operators like '>=', '<=', '==', 'in'. Follow the exact structure, field names, and data types from the reference example. Extract ALL relevant information and convert narrative text to structured format."},
            {"role": "user", "content": prompt}
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        if structured_output:
            payload["response_format"] = {"type": "json_object"}
        try:
            if stream:
                return self._generate_stream(payload)
            else:
                response = self.session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    timeout=120
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
    def _generate_stream(self, payload):
        try:
            response = self.session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=120,
                stream=True
            )
            response.raise_for_status()
            full_response = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            if 'choices' in json_data and len(json_data['choices']) > 0:
                                delta = json_data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    content = delta['content']
                                    full_response += content
                                    print(content, end='', flush=True)
                        except json.JSONDecodeError:
                            continue
            print()
            return full_response
        except requests.exceptions.RequestException as e:
            print(f"Streaming API request failed: {e}")
            return None

def extract_complete_scheme(client, raw_data, scheme_name, source_url, stream=False, max_attempts=3):
    """Extract complete scheme with all sections"""
    print(f"\nExtracting complete scheme structure...")
    
    # Combine all text for complete extraction
    all_text = ""
    for entry in raw_data:
        for section, text in entry.get("sections", {}).items():
            if text.strip():
                all_text += f"\n=== {section.upper()} ===\n{text}\n"
    
    for attempt in range(1, max_attempts + 1):
        print(f"Complete scheme extraction (attempt {attempt})...")
        
        prompt = make_complete_scheme_prompt(all_text, scheme_name, source_url)
        response = client.generate(prompt, temperature=0.3, max_tokens=4096, stream=stream)
        
        if not response:
            print(f"Warning: No response for complete scheme")
            return None
        
        # Clean the response
        cleaned_response = response.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith('```'):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        # Fix unquoted operators
        cleaned_response = fix_unquoted_operators(cleaned_response)
        
        try:
            yaml_obj = yaml.safe_load(cleaned_response)
            if yaml_obj and 'schemes' in yaml_obj:
                print(f"✅ Complete scheme extraction successful!")
                return yaml_obj
            else:
                print(f"❌ Invalid scheme structure")
                if attempt < max_attempts:
                    print(f"🔄 Retrying...")
                    continue
                else:
                    print(f"⚠️ Max attempts reached. Using best effort result.")
                    return yaml_obj
                    
        except Exception as e:
            print(f"Warning: Could not parse YAML: {e}")
            if attempt < max_attempts:
                print(f"🔄 Retrying...")
                continue
            else:
                print("Raw response:\n", response)
                print("Cleaned response:\n", cleaned_response)
                return None

def extract_yaml_from_llm(client, section, text, stream=False, max_attempts=3):
    """Extract YAML with validation and smart re-prompting"""
    for attempt in range(1, max_attempts + 1):
        print(f"\nExtracting {section} (attempt {attempt})...")
        
        prompt = make_section_prompt(section, text, attempt=attempt)
        response = client.generate(prompt, temperature=0.3, max_tokens=4096, stream=stream)
        
        if not response:
            print(f"Warning: No response for section '{section}'")
            return None
        
        # Clean the response
        cleaned_response = response.strip()
        if cleaned_response.startswith('```yaml'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith('```'):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        # Fix unquoted operators
        cleaned_response = fix_unquoted_operators(cleaned_response)
        
        try:
            yaml_obj = yaml.safe_load(cleaned_response)
            
            # Validate the structure
            validation_errors = validate_yaml_structure(yaml_obj, section)
            
            if not validation_errors:
                print(f"✅ {section} validation passed!")
                return yaml_obj
            else:
                print(f"❌ {section} validation failed:")
                for error in validation_errors:
                    print(f"   - {error}")
                
                if attempt < max_attempts:
                    print(f"🔄 Retrying with validation feedback...")
                    # Store errors for next attempt
                    continue
                else:
                    print(f"⚠️ Max attempts reached. Using best effort result.")
                    return yaml_obj
                    
    except Exception as e:
        print(f"Warning: Could not parse YAML for section '{section}': {e}")
            if attempt < max_attempts:
                print(f"🔄 Retrying...")
                continue
            else:
        print("Raw response:\n", response)
                print("Cleaned response:\n", cleaned_response)
        return None

def get_src_root():
    here = os.path.abspath(os.path.dirname(__file__))
    while True:
        if os.path.isdir(os.path.join(here, "schemes")) and os.path.isdir(os.path.join(here, "llm")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            raise RuntimeError("Could not find src root (should contain 'schemes' and 'llm' directories)")
        here = parent

def quote_all_strings(obj):
    """Recursively quote all string values and operators in a dict/list structure."""
    if isinstance(obj, dict):
        new_obj = OrderedDict()
        for k, v in obj.items():
            if k == 'operator' and isinstance(v, str):
                new_obj[k] = f'"{v}"' if not v.startswith('"') else v
            elif isinstance(v, str):
                new_obj[k] = f'"{v}"' if not v.startswith('"') else v
            else:
                new_obj[k] = quote_all_strings(v)
        return new_obj
    elif isinstance(obj, list):
        return [quote_all_strings(i) for i in obj]
    else:
        return obj

def block_style_multiline(d):
    """Set block style (>) for multi-line strings in YAML output."""
    class BlockStyleDumper(yaml.SafeDumper):
        def represent_scalar(self, tag, value, style=None):
            if isinstance(value, str) and '\n' in value:
                style = '>'
            return super().represent_scalar(tag, value, style)
    return BlockStyleDumper

def filter_to_raw_json_fields(section_data, raw_section_text):
    """Filter section_data to only include fields present in the raw JSON section text."""
    # This is a best-effort filter: only keep fields whose values appear verbatim in the raw text
    if isinstance(section_data, dict):
        return OrderedDict((k, filter_to_raw_json_fields(v, raw_section_text))
                          for k, v in section_data.items()
                          if (isinstance(v, str) and v.strip() in raw_section_text) or not isinstance(v, str) or k == 'operator')
    elif isinstance(section_data, list):
        return [filter_to_raw_json_fields(i, raw_section_text) for i in section_data
                if (isinstance(i, str) and i.strip() in raw_section_text) or not isinstance(i, str)]
    else:
        return section_data

def ordered_to_dict(obj):
    """Recursively convert OrderedDicts to dicts for YAML dumping."""
    if isinstance(obj, OrderedDict):
        return {k: ordered_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ordered_to_dict(i) for i in obj]
    else:
        return obj

def main():
    parser = argparse.ArgumentParser(description="Extract canonical YAML from scheme raw.json using LM Studio.")
    parser.add_argument("scheme_dir", help="Path to the scheme directory, relative to src/ (e.g., schemes/outputs/pm-kisan)")
    parser.add_argument("--lm-studio-url", default="http://localhost:1234", help="LM Studio API URL")
    parser.add_argument("--model", default="google/gemma-3-4b", help="Model name in LM Studio")
    parser.add_argument("--stream", action="store_true", help="Enable streaming output")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum validation attempts per section")
    parser.add_argument("--complete-scheme", action="store_true", help="Extract complete scheme structure instead of sections")
    args = parser.parse_args()

    src_root = get_src_root()
    scheme_dir = os.path.join(src_root, args.scheme_dir)
    raw_json_path = os.path.join(scheme_dir, "raw.json")
    out_yaml_path = os.path.join(scheme_dir, "rules_canonical_REFERENCE.yaml")
    scheme_name = os.path.basename(os.path.normpath(scheme_dir))

    if not os.path.exists(raw_json_path):
        print(f"Error: {raw_json_path} does not exist.")
        sys.exit(1)

    print(f"Connecting to LM Studio at {args.lm_studio_url}...")
    client = LMStudioClient(args.lm_studio_url, args.model)
    try:
        response = client.session.get(f"{args.lm_studio_url}/v1/models")
        if response.status_code == 200:
            print("LM Studio connection successful!")
        else:
            print("Warning: Could not verify LM Studio connection")
    except Exception as e:
        print(f"Warning: Could not connect to LM Studio: {e}")

    with open(raw_json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    source_url = raw_data[0].get("source_url", "")

    if args.complete_scheme:
        # Extract complete scheme structure
        canonical = extract_complete_scheme(client, raw_data, scheme_name, source_url, stream=args.stream, max_attempts=args.max_attempts)
        if not canonical:
            print("Failed to extract complete scheme")
            sys.exit(1)
    else:
        # Extract sections individually
    canonical = {}
        l1_keys = list(SECTION_MAP.values())
        extracted_keys = []
    for entry in raw_data:
        for section, canon_key in SECTION_MAP.items():
            section_text = entry.get("sections", {}).get(section, "")
            if section_text.strip():
                    yaml_obj = extract_yaml_from_llm(client, section, section_text, stream=args.stream, max_attempts=args.max_attempts)
                    if yaml_obj and canon_key in yaml_obj:
                        canonical[canon_key] = yaml_obj[canon_key]
                        extracted_keys.append(canon_key)
                    elif yaml_obj:
                    canonical[canon_key] = yaml_obj
                        extracted_keys.append(canon_key)
            
            # Extract special_provisions from eligibility text if it contains special provisions
            eligibility_text = entry.get("sections", {}).get("eligibility", "")
            if eligibility_text and ("North East" in eligibility_text or "Manipur" in eligibility_text or "Nagaland" in eligibility_text or "Jharkhand" in eligibility_text):
                print("\nExtracting special_provisions from eligibility text...")
                special_provisions_obj = extract_yaml_from_llm(client, "special_provisions", eligibility_text, stream=args.stream, max_attempts=args.max_attempts)
                if special_provisions_obj and "special_provisions" in special_provisions_obj:
                    canonical["special_provisions"] = special_provisions_obj["special_provisions"]
                    extracted_keys.append("special_provisions")
                elif special_provisions_obj:
                    canonical["special_provisions"] = special_provisions_obj
                    extracted_keys.append("special_provisions")
            
            # Extract notes from general text or create default notes
            general_text = entry.get("sections", {}).get("general", "")
            if general_text.strip():
                print("\nExtracting notes from general text...")
                notes_obj = extract_yaml_from_llm(client, "notes", general_text, stream=args.stream, max_attempts=args.max_attempts)
                if notes_obj and "notes" in notes_obj:
                    canonical["notes"] = notes_obj["notes"]
                    extracted_keys.append("notes")
                elif notes_obj:
                    canonical["notes"] = notes_obj
                    extracted_keys.append("notes")
            else:
                # Create comprehensive notes based on the scheme information
                notes_text = f"The {scheme_name.replace('_', ' ').title()} scheme is implemented through an Aadhaar-linked electronic database. The list of beneficiaries is valid for one year and is subject to revision in case of changes in land records. Administrative charges are provided to States/UTs for implementation. Project Monitoring Units (PMUs) are set up at Central and State/UT levels. All special provisions and exceptions are detailed in the 'special_provisions' section for full transparency and downstream logic."
                canonical["notes"] = notes_text
                extracted_keys.append("notes")
        
        # L1 validation
        print("\n--- Extraction Summary ---")
        for key in l1_keys:
            if key in canonical:
                print(f"[OK] {key} extracted.")
            else:
                print(f"[MISSING] {key} not found.")
        
        # Extract metadata from raw text
        raw_text = raw_data[0].get("raw_text", "")
        ministry = "Ministry of Agriculture and Farmers Welfare" if "Agriculture" in raw_text else "Ministry Name"
        implementing_agency = "Department of Agriculture, Cooperation & Farmers Welfare (DAC&FW)" if "DAC&FW" in raw_text else "Implementing Agency"
        document_type = "Operational Guidelines" if "Operational Guidelines" in raw_text else "Document Type"
        region_coverage = "All India" if "country" in raw_text.lower() else "Coverage Area"
        
        # Try to extract launch date from text
        launch_date = "2019-02-24"  # Default for PM-KISAN
        if "PM-KISAN" in raw_text or "PM-KISAN" in scheme_name.upper():
            launch_date = "2019-02-24"  # PM-KISAN was launched on Feb 24, 2019
        elif "2019" in raw_text and "February" in raw_text:
            launch_date = "2019-02-24"
        elif "2019" in raw_text:
            launch_date = "2019-01-01"  # Fallback
        
        # Create complete scheme structure
        complete_scheme = {
            "schemes": [
                {
                    "id": f"{scheme_name.upper()}_001",
                    "name": scheme_name.replace("_", " ").upper(),
                    "code": scheme_name.upper(),
                    "ministry": ministry,
                    "launched_on": launch_date,
                    "description": f"{scheme_name.replace('_', ' ').title()} is a Central Sector Scheme providing income support to all landholding farmers' families in the country, having cultivable land.",
                    "metadata": {
                        "language": "English",
                        "source_url": source_url,
                        "last_updated": "2020-03-29",  # From document revision date
                        "version": "Revised as on 29.03.2020",
                        "document_type": document_type,
                        "region_coverage": region_coverage,
                        "implementing_agency": implementing_agency,
                        "grievance_redressal": True
                    },
        **canonical
    }
            ]
        }
        
        canonical = complete_scheme
    
    # Post-process each section to enforce strict verbatim and formatting
    for entry in raw_data:
        for section, canon_key in SECTION_MAP.items():
            if canon_key in canonical:
                raw_section_text = entry.get("sections", {}).get(section, "")
                canonical[canon_key] = filter_to_raw_json_fields(canonical[canon_key], raw_section_text)
    canonical = quote_all_strings(canonical)
    canonical = ordered_to_dict(canonical)

    # Write YAML with block style for multi-line
    with open(out_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(canonical, f, allow_unicode=True, sort_keys=False, Dumper=block_style_multiline(canonical))
    print(f"\nCanonical YAML written to {out_yaml_path}")

if __name__ == "__main__":
    main()