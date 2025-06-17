# AgriSahayak++ Backend

This repository contains microservices for AgriSahayak++, an AI-powered system designed to assist farmers by automating the discovery and application process for government schemes using voice inputs.

## 📁 Services
'''
backend/
├── services/
│ ├── orchestrator/ # Handles voice file uploads and triggers data flow
│ ├── efr_db/ # Stores structured farmer records in MongoDB
│ └── (more services soon: form_filler, advisor_agent, etc.)
├── docker-compose.yml # Runs all services together
└── README.md
'''


---

##  Completed Modules

###  1. Orchestrator Service

**Path:** `services/orchestrator/`

Handles:
- Voice file uploads from users
- Stores files in the `uploads/` directory
- Mocks transcription and parsing of audio
- Sends structured data to the EFR_DB service automatically

**Endpoints:**
- `POST /upload`  
  Accepts: `farmer_id` (form field), `file` (audio file)

**Mock Workflow:**
1. Saves voice file locally.
2. Simulates transcription & information extraction (e.g., name, land size, crops).
3. Sends extracted data to the EFR_DB microservice.

---

###  2. EFR_DB Service (Farmer Record DB)

**Path:** `services/efr_db/`

Handles:
- Storing farmer details in a MongoDB database
- Exposes endpoints to add and view farmer data

**Endpoints:**
- `POST /add_farmer` — Adds a new farmer (JSON)
- `GET /farmers` — Returns all stored farmer records

Database:
- MongoDB (containerized)
- Collection: `farmers`
- Database: `agrisahayak`

---

##  Dockerized Infrastructure

The entire backend runs via Docker:

```bash
docker-compose up --build
```

## Services:

Orchestrator: http://localhost:8000

EFR_DB API: http://localhost:8001

MongoDB: accessible at mongodb://localhost:27017