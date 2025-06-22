from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Union
import os
import json

app = FastAPI()

FORMS_DIR = "forms"
os.makedirs(FORMS_DIR, exist_ok=True)

class Farmer(BaseModel):
    name: str
    contact: str
    land_size: float
    crops: List[str]
    location: str

@app.post("/fill_form")
async def fill_form(farmer_data: Union[Farmer, Dict[str, Any]]):
    """Fill form for farmer - handles both old Farmer model and new AI agent data structure"""
    
    # Handle different input formats
    if isinstance(farmer_data, dict):
        # New format from AI agent
        name = farmer_data.get("name", "Unknown Farmer")
        contact = farmer_data.get("contact", "Not provided")
        land_size = farmer_data.get("land_size", 0.0)
        crops = farmer_data.get("crops", [])
        
        # Handle location - could be string or dict
        location_data = farmer_data.get("location", {})
        if isinstance(location_data, dict):
            # Extract location string from dict
            location_parts = []
            if location_data.get("village"):
                location_parts.append(location_data["village"])
            if location_data.get("district"):
                location_parts.append(location_data["district"])
            if location_data.get("state"):
                location_parts.append(location_data["state"])
            location = ", ".join(location_parts) if location_parts else "India"
        else:
            location = str(location_data) if location_data else "India"
    else:
        # Old format (Farmer model)
        name = farmer_data.name
        contact = farmer_data.contact
        land_size = farmer_data.land_size
        crops = farmer_data.crops
        location = farmer_data.location

    # Determine appropriate scheme based on farmer data
    scheme_name = _determine_scheme(crops, land_size, farmer_data if isinstance(farmer_data, dict) else None)

    filled_form = {
        "applicant_name": name,
        "contact": contact,
        "location": location,
        "land_size": land_size,
        "crops": crops,
        "scheme": scheme_name,
        "farmer_id": farmer_data.get("farmer_id") if isinstance(farmer_data, dict) else None,
        "application_date": None,  # Will be set when actually submitted
        "status": "draft"
    }
    
    # Add scheme-specific fields
    if scheme_name == "PM-KISAN":
        filled_form.update({
            "beneficiary_type": "small_marginal_farmer" if land_size <= 2 else "farmer",
            "bank_account": "Required - to be provided",
            "aadhaar_number": "Required - to be provided"
        })
    elif scheme_name == "PMFBY":
        filled_form.update({
            "crop_season": "Kharif/Rabi - to be specified",
            "sum_insured": land_size * 50000,  # Approximate calculation
            "premium_amount": "To be calculated"
        })

    # Save as JSON file
    safe_name = name.replace(' ', '_').replace('/', '_')
    safe_scheme = scheme_name.replace(' ', '_').replace('-', '_')
    file_name = f"{safe_name}_{safe_scheme}.json"
    file_path = os.path.join(FORMS_DIR, file_name)
    
    with open(file_path, "w") as f:
        json.dump(filled_form, f, indent=2)

    return {
        "scheme_name": scheme_name,
        "filled_form": filled_form,
        "saved_to": file_path,
        "status": "form_generated"
    }

def _determine_scheme(crops: List[str], land_size: float, farmer_data: Dict = None) -> str:
    """Determine the most appropriate scheme for the farmer"""
    
    # Priority scheme selection logic
    
    # PM-KISAN for small farmers (direct income support)
    if land_size <= 2:
        return "PM-KISAN"
    
    # PMFBY for crop insurance (for main crops)
    main_crops = ["rice", "wheat", "cotton", "sugarcane", "pulses"]
    if any(crop in main_crops for crop in crops):
        return "PMFBY"
    
    # Kisan Credit Card for financial needs
    if farmer_data and any(keyword in str(farmer_data.get("extracted_text", "")).lower() 
                          for keyword in ["loan", "credit", "money", "लोन", "कर्ज"]):
        return "Kisan Credit Card"
    
    # Default to PM-KISAN for small/marginal farmers
    if land_size <= 5:
        return "PM-KISAN"
    
    # Soil Health Card for others
    return "Soil Health Card"

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "form_filler",
        "forms_directory": FORMS_DIR,
        "supported_schemes": ["PM-KISAN", "PMFBY", "Kisan Credit Card", "Soil Health Card"]
    }
