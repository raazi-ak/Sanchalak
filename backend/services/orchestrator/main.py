from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import os
import shutil
from agent import transcribe_and_parse, send_to_efr_db, send_to_form_filler, update_status  

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_voice(farmer_id: str = Form(...), file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, f"{farmer_id}_{file.filename}")
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Step 1: Parse (mock)
    parsed_farmer = transcribe_and_parse(file_location)

    # Step 2: Send to EFR_DB
    send_to_efr_db(parsed_farmer)

    # Step 3: Send to form_filler
    form_response = send_to_form_filler(parsed_farmer) 
    if not form_response:
        return JSONResponse(status_code=500, content={"error": "Form filling failed"}) 
    scheme_name = form_response.get("scheme_name")     

    # Step 4: Update status
    update_status(farmer_id, scheme_name)  

    return JSONResponse(content={
        "message": "Voice uploaded and processed",
        "path": file_location,
        "parsed_data": parsed_farmer,
        "scheme": scheme_name,
        "status": "submitted"
    })
