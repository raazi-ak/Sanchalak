from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Location(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    village: Optional[str] = None
    pincode: Optional[str] = None

class Farmer(BaseModel):
    farmer_id: str
    session_id: Optional[str] = None
    name: Optional[str] = None
    contact: Optional[str] = None
    land_size: Optional[float] = None
    crops: Optional[List[str]] = Field(default_factory=list)
    location: Optional[Location] = None
    annual_income: Optional[float] = None
    irrigation_type: Optional[str] = None
    land_ownership: Optional[str] = None
    age: Optional[int] = None
    family_size: Optional[int] = None
    extracted_text: Optional[str] = None
    language_detected: Optional[str] = None
    processed_at: Optional[float] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

class FarmerResponse(BaseModel):
    status: str
    farmer_id: str
    message: str
