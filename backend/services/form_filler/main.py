from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
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
async def fill_form(farmer: Farmer):
    scheme_name = "PM-KISAN" if "rice" in farmer.crops else "Soil Health Card"

    filled_form = {
        "applicant_name": farmer.name,
        "contact": farmer.contact,
        "location": farmer.location,
        "land_size": farmer.land_size,
        "crops": farmer.crops,
        "scheme": scheme_name
    }

    file_name = f"{farmer.name.replace(' ', '_')}_{scheme_name.replace(' ', '_')}.json"
    file_path = os.path.join(FORMS_DIR, file_name)
    with open(file_path, "w") as f:
        json.dump(filled_form, f, indent=2)

    return {
        "scheme_name": scheme_name,
        "filled_form": filled_form,
        "saved_to": file_path
    }
