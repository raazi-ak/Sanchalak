from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# In-memory DB for now (use Mongo later if needed)
status_db: Dict[str, Dict] = {}

class StatusRequest(BaseModel):
    farmer_id: str
    scheme_name: str
    status: str  # e.g., 'pending', 'submitted', 'approved', 'rejected'

@app.post("/update_status")
async def update_status(req: StatusRequest):
    status_db[req.farmer_id] = {
        "scheme": req.scheme_name,
        "status": req.status
    }
    return {"message": "Status updated", "record": status_db[req.farmer_id]}

@app.get("/status/{farmer_id}")
async def get_status(farmer_id: str):
    if farmer_id in status_db:
        return {"farmer_id": farmer_id, **status_db[farmer_id]}
    raise HTTPException(status_code=404, detail="Status not found")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "status_tracker",
        "records_count": len(status_db)
    }
