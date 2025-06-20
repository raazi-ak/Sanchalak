import random
import requests

def transcribe_and_parse(filepath):
    # 🔁 Mocking transcription and parsing
    # Normally you would do voice-to-text and NLP here

    # Generate a fake farmer from audio
    farmers = [
        {
            "name": "Ramesh",
            "contact": "9876543210",
            "land_size": 2.5,
            "crops": ["rice", "groundnut"],
            "location": "Tamil Nadu"
        },
        {
            "name": "Anita",
            "contact": "9994432111",
            "land_size": 1.2,
            "crops": ["millet", "cotton"],
            "location": "Andhra Pradesh"
        },
        {
            "name": "Suresh",
            "contact": "8787878787",
            "land_size": 3.8,
            "crops": ["wheat"],
            "location": "Karnataka"
        }
    ]
    return random.choice(farmers)

def send_to_efr_db(farmer_data):
    url = "http://efr_db:8001/add_farmer"
    try:
        response = requests.post(url, json=farmer_data)
        print("✅ Sent to EFR_DB:", response.status_code, response.json())
    except Exception as e:
        print("❌ Error sending to EFR_DB:", str(e))

def send_to_form_filler(farmer_data):
    url = "http://form_filler:8002/fill_form"
    try:
        response = requests.post(url, json=farmer_data)
        return response.json()  # 👈 RETURN the response!
    except Exception as e:
        print("❌ Error sending to form_filler:", str(e))
        return {"scheme_name": None}

def update_status(farmer_id, scheme_name):
    url = "http://status_tracker:8003/update_status"
    payload = {
        "farmer_id": farmer_id,
        "scheme_name": scheme_name,
        "status": "submitted"
    }
    try:
        response = requests.post(url, json=payload)
        print("📬 Status Tracker Response:", response.status_code, response.json())
    except Exception as e:
        print("❌ Error sending to status_tracker:", str(e))

