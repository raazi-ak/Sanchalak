from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Header, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError
import os
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import json

from models import (
    Farmer, FarmerSearchQuery, FarmerSummary,
    DatabaseResponse, BulkFarmerResponse, ProcessingStatus
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Enhanced Farmer Registry (EFR) Database",
    description="Comprehensive farmer database with advanced search and analytics",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "agrisahayak")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "farmers")

# Global database connection
client = None
db = None
collection = None
database_ready = False

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    global client, db, collection, database_ready
    
    try:
        logger.info("🔍 Checking MongoDB availability...")
        
        # First, try to connect to MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        
        # Test connection with timeout
        client.admin.command('ping')
        
        logger.info("✅ MongoDB is available")
        
        # Now set up the database and collection
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        # Create indexes for better performance
        await create_indexes()
        
        database_ready = True
        logger.info("✅ Database connected successfully")
        
    except Exception as e:
        logger.error(f"❌ CRITICAL: Failed to connect to database: {str(e)}")
        logger.error("🚨 Server cannot start without database connection. Terminating...")
        logger.error("💡 Make sure MongoDB is running: brew services start mongodb-community")
        import sys
        sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connection on shutdown"""
    global client, database_ready
    
    if client:
        try:
            logger.info("Closing database connection...")
            client.close()
            database_ready = False
            logger.info("✅ Database connection closed")
        except Exception as e:
            logger.warning(f"Warning: Error closing database connection: {str(e)}")

async def create_indexes():
    """Create database indexes for optimal performance"""
    try:
        collection.create_index([("farmer_id", ASCENDING)], unique=True)
        collection.create_index([("contact", ASCENDING)])
        collection.create_index([("phone_number", ASCENDING)])
        collection.create_index([("state", ASCENDING)])
        collection.create_index([("district", ASCENDING)])
        collection.create_index([("crops", ASCENDING)])
        collection.create_index([("status", ASCENDING)])
        collection.create_index([("created_at", DESCENDING)])
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.warning(f"Failed to create indexes: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Enhanced Farmer Registry (EFR) Database",
        "version": "2.0.0",
        "status": "ready" if database_ready else "initializing",
        "timestamp": datetime.utcnow().isoformat(),
        "database": {
            "connected": database_ready,
            "uri": MONGO_URI.replace("://", "://***@") if "@" in MONGO_URI else MONGO_URI,
            "database": DATABASE_NAME,
            "collection": COLLECTION_NAME
        }
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        if not database_ready or not client:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "Database not connected",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Test database connection
        client.admin.command('ping')
        
        # Get basic stats
        farmer_count = collection.count_documents({})
        
        return JSONResponse(content={
            "status": "healthy",
            "database_connected": True,
            "total_farmers": farmer_count,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.post("/add_farmer", response_model=DatabaseResponse)
async def add_farmer(farmer_data: Union[Farmer, Dict[str, Any]]):
    """
    Add a new farmer to the database
    """
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        # Handle different input types
        if isinstance(farmer_data, dict):
            # Convert dict to farmer
            farmer = Farmer(**farmer_data)
        else:
            # Already farmer object
            farmer = farmer_data
        
        # Check for existing farmer
        existing_farmer = collection.find_one({
            "$or": [
                {"farmer_id": farmer.farmer_id},
                {"aadhaar_number": farmer.aadhaar_number},
                {"phone_number": farmer.phone_number}
            ]
        })
        
        if existing_farmer:
            return DatabaseResponse(
                success=False,
                message="Farmer already exists",
                error="Duplicate farmer found"
            )
        
        # Insert into database
        farmer_dict = farmer.dict()
        farmer_dict["_id"] = farmer.farmer_id
        
        result = collection.insert_one(farmer_dict)
        
        logger.info(f"✅ Farmer added: {farmer.farmer_id}")
        
        return DatabaseResponse(
            success=True,
            message="Farmer added successfully",
            data={
                "farmer_id": farmer.farmer_id,
                "id": str(result.inserted_id)
            }
        )
        
    except DuplicateKeyError:
        return DatabaseResponse(
            success=False,
            message="Farmer with this ID already exists",
            error="Duplicate farmer_id"
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to add farmer: {str(e)}")
        return DatabaseResponse(
            success=False,
            message="Failed to add farmer",
            error=str(e)
        )

@app.get("/farmers", response_model=List[Farmer])
async def list_farmers(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    state: Optional[str] = None,
    district: Optional[str] = None,
    status: Optional[ProcessingStatus] = None
):
    """List farmers with optional filtering"""
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        # Build query filter
        query_filter = {}
        
        if state:
            query_filter["state"] = {"$regex": state, "$options": "i"}
        if district:
            query_filter["district"] = {"$regex": district, "$options": "i"}
        if status:
            query_filter["status"] = status
        
        # Execute query
        cursor = collection.find(query_filter, {"_id": 0}).skip(offset).limit(limit)
        farmers = list(cursor)
        
        # Convert to enhanced farmer profiles
        enhanced_farmers = []
        for farmer_data in farmers:
            try:
                enhanced_farmers.append(Farmer(**farmer_data))
            except Exception as e:
                logger.warning(f"Failed to convert farmer data: {str(e)}")
                continue
        
        return enhanced_farmers
        
    except Exception as e:
        logger.error(f"❌ Failed to list farmers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/farmer/{farmer_id}", response_model=Farmer)
async def get_farmer(farmer_id: str):
    """Get a specific farmer by ID"""
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        farmer_data = collection.find_one({"farmer_id": farmer_id}, {"_id": 0})
        
        if not farmer_data:
            raise HTTPException(status_code=404, detail="Farmer not found")
        
        return Farmer(**farmer_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get farmer {farmer_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/farmer/{farmer_id}", response_model=DatabaseResponse)
async def update_farmer(farmer_id: str, farmer_data: Union[Farmer, Dict[str, Any]]):
    """Update an existing farmer (robust merge)"""
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    try:
        # Fetch existing record
        existing = collection.find_one({"farmer_id": farmer_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Farmer not found")
        # Convert to dict if needed
        if not isinstance(existing, dict):
            existing = dict(existing)
        # Prepare update data
        if isinstance(farmer_data, dict):
            update_data = farmer_data
        else:
            update_data = farmer_data.dict(exclude_unset=True)
        # Merge: update only provided fields
        merged = {**existing, **update_data}
        merged["updated_at"] = datetime.utcnow()
        # Validate (optional, but recommended)
        try:
            Farmer(**merged)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {e}")
        # Save merged record
        result = collection.replace_one({"farmer_id": farmer_id}, merged)
        if result.modified_count > 0:
            logger.info(f"✅ Farmer updated (robust): {farmer_id}")
            return DatabaseResponse(
                success=True,
                message="Farmer updated successfully",
                data={"farmer_id": farmer_id, "modified_count": result.modified_count}
            )
        else:
            return DatabaseResponse(
                success=False,
                message="No changes made",
                data={"farmer_id": farmer_id}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update farmer {farmer_id}: {str(e)}")
        return DatabaseResponse(
            success=False,
            message="Failed to update farmer",
            error=str(e)
        )

@app.delete("/farmer/{farmer_id}", response_model=DatabaseResponse)
async def delete_farmer(farmer_id: str):
    """Delete a farmer by ID"""
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        result = collection.delete_one({"farmer_id": farmer_id})
        
        if result.deleted_count > 0:
            logger.info(f"✅ Farmer deleted: {farmer_id}")
            return DatabaseResponse(
                success=True,
                message="Farmer deleted successfully",
                data={"farmer_id": farmer_id}
            )
        else:
            raise HTTPException(status_code=404, detail="Farmer not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete farmer {farmer_id}: {str(e)}")
        return DatabaseResponse(
            success=False,
            message="Failed to delete farmer",
            error=str(e)
        )

@app.delete("/farmers/clear", response_model=DatabaseResponse)
async def clear_all_farmers(admin_key: str = Header(..., description="Admin key required for database operations")):
    """Clear all farmer records from the database (ADMIN ONLY)"""
    
    # Simple admin key protection - in production, use proper JWT or OAuth
    ADMIN_KEY = "thisisourhardworkpleasedontcopy"  # This should be in environment variables
    
    if admin_key != ADMIN_KEY:
        logger.warning(f"❌ Unauthorized clear attempt with key: {admin_key[:10]}...")
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid admin key")
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        # Count records before deletion
        count_before = collection.count_documents({})
        logger.warning(f"🗑️  ADMIN: Clearing {count_before} farmer records...")
        
        if count_before > 0:
            # Delete all records
            result = collection.delete_many({})
            logger.warning(f"✅ ADMIN: Successfully deleted {result.deleted_count} farmer records")
            
            return DatabaseResponse(
                success=True,
                message=f"Successfully deleted {result.deleted_count} farmer records",
                data={"deleted_count": result.deleted_count, "total_before": count_before}
            )
        else:
            return DatabaseResponse(
                success=True,
                message="Database is already empty",
                data={"deleted_count": 0, "total_before": 0}
            )
        
    except Exception as e:
        logger.error(f"❌ Error clearing database: {str(e)}")
        return DatabaseResponse(
            success=False,
            message="Failed to clear database",
            error=str(e)
        )

@app.post("/search", response_model=List[Farmer])
async def search_farmers(search_query: FarmerSearchQuery):
    """Advanced farmer search with multiple criteria"""
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        # Build MongoDB query
        query_filter = {}
        
        if search_query.name:
            query_filter["name"] = {"$regex": search_query.name, "$options": "i"}
        
        if search_query.state:
            query_filter["state"] = {"$regex": search_query.state, "$options": "i"}
        
        if search_query.district:
            query_filter["district"] = {"$regex": search_query.district, "$options": "i"}
        
        if search_query.crops:
            query_filter["crops"] = {"$in": search_query.crops}
        
        if search_query.land_size_min is not None or search_query.land_size_max is not None:
            land_filter = {}
            if search_query.land_size_min is not None:
                land_filter["$gte"] = search_query.land_size_min
            if search_query.land_size_max is not None:
                land_filter["$lte"] = search_query.land_size_max
            query_filter["land_size_acres"] = land_filter
        
        if search_query.status:
            query_filter["status"] = search_query.status
        
        if search_query.created_after or search_query.created_before:
            date_filter = {}
            if search_query.created_after:
                date_filter["$gte"] = search_query.created_after
            if search_query.created_before:
                date_filter["$lte"] = search_query.created_before
            query_filter["created_at"] = date_filter
        
        # Execute search
        cursor = collection.find(query_filter, {"_id": 0}).skip(search_query.offset).limit(search_query.limit)
        farmers = list(cursor)
        
        # Convert to enhanced farmer profiles
        farmer_list = []
        for farmer_data in farmers:
            try:
                farmer_list.append(Farmer(**farmer_data))
            except Exception as e:
                logger.warning(f"Failed to convert farmer data: {str(e)}")
                continue
        
        return farmer_list
        
    except Exception as e:
        logger.error(f"❌ Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summary", response_model=FarmerSummary)
async def get_farmer_summary():
    """Get summary statistics for all farmers"""
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        # Aggregation pipeline for statistics
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_farmers": {"$sum": 1},
                    "total_land_size": {"$sum": "$land_size_acres"},
                    "average_land_size": {"$avg": "$land_size_acres"},
                    "states": {"$push": "$state"},
                    "statuses": {"$push": "$status"},
                    "all_crops": {"$push": "$crops"}
                }
            }
        ]
        
        result = list(collection.aggregate(pipeline))
        
        if not result:
            return FarmerSummary(
                total_farmers=0,
                average_land_size=0.0,
                total_land_size=0.0
            )
        
        data = result[0]
        
        # Count by state
        by_state = {}
        for state in data.get("states", []):
            if state:
                by_state[state] = by_state.get(state, 0) + 1
        
        # Count by status
        by_status = {}
        for status in data.get("statuses", []):
            if status:
                by_status[status] = by_status.get(status, 0) + 1
        
        # Count by crops
        by_crops = {}
        for crops_list in data.get("all_crops", []):
            if crops_list:
                for crop in crops_list:
                    by_crops[crop] = by_crops.get(crop, 0) + 1
        
        return FarmerSummary(
            total_farmers=data.get("total_farmers", 0),
            average_land_size=data.get("average_land_size", 0.0),
            total_land_size=data.get("total_land_size", 0.0),
            by_state=by_state,
            by_status=by_status,
            by_crops=by_crops
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def get_metrics():
    """Get database metrics and performance stats"""
    
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        # Basic stats
        total_farmers = collection.count_documents({})
        
        # Recent activity (last 24 hours)
        recent_cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_farmers = collection.count_documents({"created_at": {"$gte": recent_cutoff}})
        
        # Database stats
        db_stats = db.command("dbStats")
        
        return {
            "database_ready": database_ready,
            "total_farmers": total_farmers,
            "farmers_added_today": recent_farmers,
            "database_size_mb": round(db_stats.get("dataSize", 0) / 1024 / 1024, 2),
            "indexes": db_stats.get("indexes", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get metrics: {str(e)}")
        return {
            "database_ready": database_ready,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.patch("/farmer/{farmer_id}", response_model=DatabaseResponse)
async def patch_farmer(farmer_id: str, update_data: dict = Body(...)):
    """Safely update only provided fields for a farmer (partial update)"""
    if not database_ready:
        raise HTTPException(status_code=503, detail="Database not ready")
    try:
        # Fetch existing record
        existing = collection.find_one({"farmer_id": farmer_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Farmer not found")
        # Do not allow changing farmer_id or _id
        update_data.pop("farmer_id", None)
        update_data.pop("_id", None)
        # Validate update (optional: merge and validate)
        merged = {**existing, **update_data}
        try:
            Farmer(**merged)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {e}")
        # Perform update
        result = collection.update_one({"farmer_id": farmer_id}, {"$set": update_data})
        if result.modified_count > 0:
            logger.info(f"✅ Farmer PATCH updated: {farmer_id}")
            return DatabaseResponse(
                success=True,
                message="Farmer updated successfully (PATCH)",
                data={"farmer_id": farmer_id, "modified_count": result.modified_count}
            )
        else:
            return DatabaseResponse(
                success=False,
                message="No changes made (PATCH)",
                data={"farmer_id": farmer_id}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to PATCH update farmer {farmer_id}: {str(e)}")
        return DatabaseResponse(
            success=False,
            message="Failed to PATCH update farmer",
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
