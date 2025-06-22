from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from models import Farmer, FarmerResponse, Location
from typing import Dict, Any
import os
from datetime import datetime

app = FastAPI(title="EFR Database", description="Electronic Farmer Records Database", version="1.0.0")

# Connect to MongoDB
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://mongo:27017")
client = MongoClient(MONGO_URI)
db = client["agrisahayak"]
collection = db["farmers"]

@app.post("/add_farmer", response_model=FarmerResponse)
async def add_farmer(farmer_data: Dict[str, Any]):
    """Add or update farmer data from AI Agent processing"""
    try:
        farmer_id = farmer_data.get("farmer_id")
        if not farmer_id:
            raise HTTPException(status_code=400, detail="farmer_id is required")
        
        # Convert location dict to Location object if present
        if "location" in farmer_data and isinstance(farmer_data["location"], dict):
            farmer_data["location"] = Location(**farmer_data["location"]).dict()
        
        # Add timestamps
        farmer_data["updated_at"] = datetime.utcnow()
        if not farmer_data.get("created_at"):
            farmer_data["created_at"] = datetime.utcnow()
        
        # Check if farmer already exists
        existing_farmer = collection.find_one({"farmer_id": farmer_id})
        
        if existing_farmer:
            # Update existing farmer
            result = collection.update_one(
                {"farmer_id": farmer_id},
                {"$set": farmer_data}
            )
            if result.modified_count > 0:
                return FarmerResponse(
                    status="updated",
                    farmer_id=farmer_id,
                    message="Farmer data updated successfully"
                )
            else:
                return FarmerResponse(
                    status="no_change",
                    farmer_id=farmer_id,
                    message="No changes detected"
                )
        else:
            # Insert new farmer
            result = collection.insert_one(farmer_data)
            return FarmerResponse(
                status="created",
                farmer_id=farmer_id,
                message="Farmer data created successfully"
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/farmer/{farmer_id}")
async def get_farmer(farmer_id: str):
    """Get farmer by farmer_id"""
    farmer = collection.find_one({"farmer_id": farmer_id}, {"_id": 0})
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    return farmer

@app.get("/farmers")
async def list_farmers(limit: int = 100, skip: int = 0):
    """List all farmers with pagination"""
    farmers = list(collection.find({}, {"_id": 0}).skip(skip).limit(limit))
    total_count = collection.count_documents({})
    return {
        "farmers": farmers,
        "total": total_count,
        "limit": limit,
        "skip": skip
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        client.admin.command('ping')
        total_farmers = collection.count_documents({})
        return {
            "status": "healthy",
            "service": "efr_db",
            "database": "connected",
            "total_farmers": total_farmers,
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "efr_db",
            "database": "disconnected",
            "error": str(e)
        }
