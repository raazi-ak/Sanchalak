#!/usr/bin/env python3

import yaml
import os

def fix_generated_yaml(input_path, output_path):
    """Fix the generated YAML by adding missing sections and wrapping in complete scheme structure"""
    
    # Read the generated YAML
    with open(input_path, 'r', encoding='utf-8') as f:
        generated_data = yaml.safe_load(f)
    
    # Create the complete scheme structure
    complete_scheme = {
        "schemes": [
            {
                "id": "PM_KISAN_001",
                "name": "PM-KISAN",
                "code": "PMKISAN",
                "ministry": "Ministry of Agriculture and Farmers Welfare",
                "launched_on": "2019-02-24",
                "description": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN) is a Central Sector Scheme providing income support to all landholding farmers' families in the country, having cultivable land.",
                "metadata": {
                    "language": "English",
                    "source_url": generated_data.get("source_url", ""),
                    "last_updated": "2020-03-29",
                    "version": "Revised as on 29.03.2020",
                    "document_type": "Operational Guidelines",
                    "region_coverage": "All India",
                    "implementing_agency": "Department of Agriculture, Cooperation & Farmers Welfare (DAC&FW)",
                    "grievance_redressal": True
                },
                "eligibility": generated_data.get("eligibility", {}),
                "special_provisions": [
                    {
                        "region": "North East States",
                        "description": "In North Eastern States, where land ownership rights are community-based and it may not be possible to assess the quantum of landholder farmers, an alternate implementation mechanism for eligibility will be developed and approved by a Committee of Union Ministers and State Chief Ministers or their representatives, based on proposals by the concerned North Eastern States."
                    },
                    {
                        "region": "Manipur",
                        "description": "For identification of bona fide beneficiaries under PM-Kisan Scheme in Manipur, a certificate issued by the Village authority (Chairman/Chief) authorizing any tribal family to cultivate a piece of land may be accepted. Such certification must be authenticated by the concerned sub-divisional officers."
                    },
                    {
                        "region": "Nagaland",
                        "description": "For community-owned cultivable land in Nagaland under permanent cultivation, a certificate issued by the village council/authority/village chieftain regarding land holding, duly verified by the administrative head of the circle/sub-division and countersigned by the Deputy Commissioner of the District, shall suffice. For Jhum land (as per Section–2(7) of the Nagaland Jhum Land Act, 1970), identification is based on certification by the village council/chief/head, verified and countersigned as above, and the beneficiary must be included in the state's Agriculture Census of 2015-16."
                    },
                    {
                        "region": "Jharkhand",
                        "description": "In Jharkhand, the farmer must submit a 'Vanshavali (Lineage)' linked to the entry of land record comprising their ancestor's name, giving a chart of successor. This lineage chart is submitted before the Gram Sabha for objections, then verified by village/circle revenue officials and countersigned by the District revenue authority. Names are uploaded to the PM-Kisan portal after verification and subject to exclusion criteria."
                    }
                ],
                "benefits": generated_data.get("benefits", []),
                "documents": generated_data.get("documents", []),
                "application_modes": generated_data.get("application_modes", []),
                "monitoring": generated_data.get("monitoring", {}),
                "notes": "The scheme is implemented through an Aadhaar-linked electronic database. The list of beneficiaries is valid for one year and is subject to revision in case of changes in land records. Administrative charges are provided to States/UTs for implementation. Project Monitoring Units (PMUs) are set up at Central and State/UT levels. All special provisions and exceptions are detailed in the 'special_provisions' section for full transparency and downstream logic."
            }
        ]
    }
    
    # Fix operator quoting in eligibility rules
    if "eligibility" in complete_scheme["schemes"][0] and "rules" in complete_scheme["schemes"][0]["eligibility"]:
        for rule in complete_scheme["schemes"][0]["eligibility"]["rules"]:
            if "operator" in rule:
                # Ensure operator is quoted
                if not isinstance(rule["operator"], str) or not rule["operator"].startswith('"'):
                    rule["operator"] = f'"{rule["operator"]}"'
    
    # Write the complete scheme
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(complete_scheme, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    print(f"✅ Fixed YAML written to {output_path}")

if __name__ == "__main__":
    input_path = "src/schemes/outputs/pm-kisan/rules_canonical_REFERENCE.yaml"
    output_path = "src/schemes/outputs/pm-kisan/rules_canonical_COMPLETE.yaml"
    
    if os.path.exists(input_path):
        fix_generated_yaml(input_path, output_path)
    else:
        print(f"Error: {input_path} does not exist") 