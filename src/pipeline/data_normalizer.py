"""
Data Normalizer Module

Normalizes farmer data for downstream processing.

Converts EFR database data to Prolog-compatible atomic values.
Handles data type conversion, standardization, and validation.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class DataNormalizer:
    """Normalizes EFR data to Prolog-compatible atomic values."""
    
    def __init__(self):
        """Initialize the data normalizer."""
        # Define standard enums for Prolog compatibility (general names)
        self.land_ownership_map = {
            "owned": "owned",
            "lease": "leased", 
            "leased": "leased",
            "sharecropping": "sharecropping",
            "joint": "joint",
            "unknown": "unknown",
            "not specified": "unknown"
        }
        
        self.irrigation_type_map = {
            "rain fed": "rain_fed",
            "rainfed": "rain_fed", 
            "canal": "canal",
            "borewell": "borewell",
            "well": "well",
            "drip": "drip",
            "drip irrigation": "drip",
            "sprinkler": "sprinkler",
            "sprinkler irrigation": "sprinkler",
            "tube well": "tube_well",
            "tubewell": "tube_well",
            "surface": "surface",
            "surface irrigation": "surface",
            "flood": "flood",
            "flood irrigation": "flood",
            "unknown": "unknown",
            "not specified": "unknown"
        }
        
        self.boolean_map = {
            "yes": True,
            "y": True,
            "true": True,
            "1": True,
            "no": False,
            "n": False,
            "false": False,
            "0": False
        }
    
    def normalize_farmer_data(self, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize farmer data from EFR to Prolog-compatible format.
        
        Args:
            farmer_data: Raw farmer data from EFR
            
        Returns:
            Normalized data with atomic values
        """
        normalized = {}
        
        try:
            # Basic fields
            normalized["farmer_id"] = str(farmer_data.get("farmer_id", ""))
            normalized["name"] = str(farmer_data.get("name", "Unknown"))
            
            # Age (convert to integer)
            age = farmer_data.get("age")
            if age is not None:
                try:
                    normalized["age"] = int(float(age))
                except (ValueError, TypeError):
                    normalized["age"] = None
            
            # Gender (standardize)
            gender = farmer_data.get("gender", "").lower().strip()
            if gender in ["male", "female", "other"]:
                normalized["gender"] = gender
            else:
                normalized["gender"] = None
            
            # Phone number (clean)
            phone = farmer_data.get("phone_number") or farmer_data.get("contact")
            if phone:
                # Remove spaces, dashes, etc.
                clean_phone = re.sub(r'[^\d+]', '', str(phone))
                if clean_phone:
                    normalized["phone_number"] = clean_phone
                else:
                    normalized["phone_number"] = None
            else:
                normalized["phone_number"] = None
            
            # Family members (atomic data)
            family_members = farmer_data.get("family_members", [])
            if isinstance(family_members, list):
                normalized["family_members"] = family_members
            else:
                normalized["family_members"] = []
            
            # Legacy support for family_size and dependents
            family_size = farmer_data.get("family_size")
            if family_size is not None:
                try:
                    normalized["family_size"] = int(float(family_size))
                except (ValueError, TypeError):
                    normalized["family_size"] = None
            else:
                normalized["family_size"] = None
                
            dependents = farmer_data.get("dependents")
            if dependents is not None:
                try:
                    normalized["dependents"] = int(float(dependents))
                except (ValueError, TypeError):
                    normalized["dependents"] = None
            else:
                normalized["dependents"] = None
            
            # Location fields
            for field in ["state", "district", "village", "pincode"]:
                value = farmer_data.get(field)
                if value:
                    normalized[field] = str(value).strip()
                else:
                    normalized[field] = None
            
            # Land size (convert to float)
            land_size = farmer_data.get("land_size_acres") or farmer_data.get("land_size")
            if land_size is not None:
                try:
                    normalized["land_size_acres"] = float(land_size)
                except (ValueError, TypeError):
                    normalized["land_size_acres"] = None
            else:
                normalized["land_size_acres"] = None
            
            # Land ownership (map to enum)
            ownership = farmer_data.get("land_ownership", "").lower().strip()
            normalized["land_ownership"] = self.land_ownership_map.get(ownership, "unknown")
            
            # Crops (ensure list)
            crops = farmer_data.get("crops", [])
            if isinstance(crops, str):
                # Split comma-separated string
                crops = [crop.strip() for crop in crops.split(",") if crop.strip()]
            elif not isinstance(crops, list):
                crops = []
            normalized["crops"] = crops
            
            # Farming equipment (ensure list)
            equipment = farmer_data.get("farming_equipment", [])
            if isinstance(equipment, str):
                equipment = [item.strip() for item in equipment.split(",") if item.strip()]
            elif not isinstance(equipment, list):
                equipment = []
            normalized["farming_equipment"] = equipment
            
            # Irrigation type (map to enum)
            irrigation = farmer_data.get("irrigation_type", "").lower().strip()
            normalized["irrigation_type"] = self.irrigation_type_map.get(irrigation, "unknown")
            
            # Annual income (convert to float)
            income = farmer_data.get("annual_income")
            if income is not None:
                try:
                    normalized["annual_income"] = float(income)
                except (ValueError, TypeError):
                    normalized["annual_income"] = None
            else:
                normalized["annual_income"] = None
            
            # Boolean fields
            for field in ["bank_account", "has_kisan_credit_card"]:
                value = farmer_data.get(field)
                if value is not None:
                    if isinstance(value, bool):
                        normalized[field] = value
                    elif isinstance(value, str):
                        normalized[field] = self.boolean_map.get(value.lower().strip(), None)
                    else:
                        normalized[field] = bool(value)
                else:
                    normalized[field] = None
            
            # Add metadata
            normalized["normalized_at"] = datetime.utcnow().isoformat()
            normalized["original_data"] = farmer_data
            
            logger.info(f"✅ Normalized data for farmer {normalized['farmer_id']}")
            return normalized
            
        except Exception as e:
            logger.error(f"❌ Failed to normalize farmer data: {str(e)}")
            return {
                "farmer_id": str(farmer_data.get("farmer_id", "unknown")),
                "name": "Unknown",
                "error": str(e),
                "normalized_at": datetime.utcnow().isoformat()
            }
    
    def create_prolog_facts(self, normalized_data: Dict[str, Any]) -> List[str]:
        """
        Create Prolog facts from normalized data.
        
        Args:
            normalized_data: Normalized farmer data
            
        Returns:
            List of Prolog fact strings
        """
        facts = []
        farmer_id = normalized_data.get("farmer_id", "unknown")
        
        # Person fact
        facts.append(f"person('{farmer_id}').")
        
        # Individual field facts
        field_mappings = {
            "name": "name",
            "age": "age", 
            "gender": "gender",
            "phone_number": "phone_number",
            "family_size": "family_size",
            "dependents": "dependents",
            "state": "state",
            "district": "district", 
            "village": "village",
            "pincode": "pincode",
            "land_size_acres": "land_size_acres",
            "land_ownership": "land_ownership",
            "irrigation_type": "irrigation_type",
            "annual_income": "annual_income",
            "bank_account": "bank_account",
            "has_kisan_credit_card": "has_kisan_credit_card"
        }
        
        for field, prolog_field in field_mappings.items():
            value = normalized_data.get(field)
            if value is not None:
                if isinstance(value, bool):
                    facts.append(f"{prolog_field}('{farmer_id}', {str(value).lower()}).")
                elif isinstance(value, (int, float)):
                    facts.append(f"{prolog_field}('{farmer_id}', {value}).")
                else:
                    # Escape quotes in strings
                    safe_value = str(value).replace("'", "\\'")
                    facts.append(f"{prolog_field}('{farmer_id}', '{safe_value}').")
        
        # Handle lists (crops, farming_equipment)
        for field in ["crops", "farming_equipment"]:
            items = normalized_data.get(field, [])
            if items:
                for item in items:
                    safe_item = str(item).replace("'", "\\'")
                    facts.append(f"{field}_item('{farmer_id}', '{safe_item}').")
        
        # Handle family members (atomic facts)
        family_members = normalized_data.get("family_members", [])
        for member in family_members:
            if isinstance(member, dict):
                relation = member.get("relation", "unknown")
                name = member.get("name", "unknown")
                age = member.get("age")
                
                safe_relation = str(relation).replace("'", "\\'")
                safe_name = str(name).replace("'", "\\'")
                
                if age is not None:
                    try:
                        age_int = int(float(age))
                        facts.append(f"family_member('{farmer_id}', '{safe_relation}', '{safe_name}', {age_int}).")
                    except (ValueError, TypeError):
                        facts.append(f"family_member('{farmer_id}', '{safe_relation}', '{safe_name}', unknown).")
                else:
                    facts.append(f"family_member('{farmer_id}', '{safe_relation}', '{safe_name}', unknown).")
        
        return facts
    
    def validate_required_fields(self, normalized_data: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that required fields are present and valid.
        
        Args:
            normalized_data: Normalized farmer data
            required_fields: List of required field names
            
        Returns:
            Tuple of (is_valid, missing_fields)
        """
        missing_fields = []
        
        for field in required_fields:
            value = normalized_data.get(field)
            if value is None or value == "":
                missing_fields.append(field)
        
        is_valid = len(missing_fields) == 0
        return is_valid, missing_fields 