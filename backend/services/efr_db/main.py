from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from models import Farmer
import os

app = FastAPI()

# Connect to MongoDB
client = MongoClient(os.getenv("MONGO_URI", "mongodb://mongo:27017"))
db = client["agrisahayak"]
collection = db["farmers"]

@app.post("/add_farmer")
async def add_farmer(farmer: Farmer):
    if collection.find_one({"contact": farmer.contact}):
        raise HTTPException(status_code=400, detail="Farmer already exists")
    
    result = collection.insert_one(farmer.dict())
    return {"message": "Farmer added", "id": str(result.inserted_id)}

@app.get("/farmers")
async def list_farmers():
    return list(collection.find({}, {"_id": 0}))
