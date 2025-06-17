from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import os
import shutil
from agent import transcribe_and_parse, send_to_efr_db

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_voice(farmer_id: str = Form(...), file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, f"{farmer_id}_{file.filename}")
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ⛏️ MOCK: Transcribe + Parse + Send to DB
    parsed_farmer = transcribe_and_parse(file_location)
    send_to_efr_db(parsed_farmer)

    return JSONResponse(content={
        "message": "Voice uploaded and processed",
        "path": file_location,
        "parsed_data": parsed_farmer
    })
