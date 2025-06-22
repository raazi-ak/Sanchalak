# 🌟 **SANCHALAK SYSTEM ARCHITECTURE & FLOW**
## *Complete Technical Reference Guide*

---

## 🎯 **SYSTEM PURPOSE**
**Sanchalak = AI-powered government scheme assistant for Indian farmers**

- **Input**: Farmers speak in their native language via Telegram
- **Processing**: AI processes their info and finds eligible government schemes  
- **Output**: Auto-generates and submits applications + tracks status
- **Languages**: 15+ Indian languages supported
- **Goal**: Bridge technology gap for rural farmers accessing government benefits

---

## 🏗️ **SYSTEM ARCHITECTURE OVERVIEW**

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   FARMER    │───▶│ TELEGRAM    │───▶│ORCHESTRATOR │───▶│  AI AGENT   │
│ (Voice/Text)│    │    BOT      │    │(Coordinator)│    │(Real Brain) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │                  │
                    ┌─────────────────────────┼──────────────────┘
                    │                         ▼
         ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
         │EFR DATABASE │    │FORM FILLER  │    │STATUS       │
         │ (Records)   │    │(Applications│    │TRACKER      │
         └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                              ┌─────────────────────────────────┐
                              │        MONITORING              │
                              │    (Health Dashboard)          │
                              └─────────────────────────────────┘
```

---

## 📋 **COMPONENT BREAKDOWN**

### **1. 📱 Telegram Bot (Gateway & UI)**
- **Location**: `components/telegram-bot/`
- **Port**: 8080
- **Purpose**: Primary user interface and session management
- **Features**:
  - Multilingual support (15+ Indian languages)
  - Voice message handling
  - User registration and verification
  - Session management
  - Response formatting

**Key Models**:
```python
FarmerVerification:
  - farmer_id: "farmer_abc123"
  - telegram_user_id: 123456789
  - phone: "+919876543210"
  - name: "राम शर्मा"
  - language_preference: "hi"
  - verification_status: "verified"
  - ekyc_status: "aadhaar_verified"

SessionLog:
  - session_id: "session_xyz789"
  - farmer_id: "farmer_abc123"
  - messages: [voice/text messages]
  - processing_result: {AI response}
```

### **2. 🎼 Orchestrator (Coordinator)**
- **Location**: `components/orchestrator/`
- **Port**: 8000
- **Purpose**: Coordinates entire processing pipeline
- **Current State**: Uses mock AI functions
- **Future State**: Integrates with real AI Agent

**Current Mock Functions**:
```python
transcribe_and_parse(filepath) → Fake farmer data
_analyze_farmer_content() → Fake scheme matching
_mock_voice_transcription() → Fake transcriptions
```

**Real Integration Target**:
```python
ai_agent.process_audio() → Real Whisper transcription
ai_agent.extract_information() → Real NLP extraction
ai_agent.check_eligibility() → Real scheme matching
```

### **3. 🧠 AI Agent (The Real Brain)**
- **Location**: `agent/` → `components/ai-agent/`
- **Port**: 8004 (planned)
- **Purpose**: Complete AI processing pipeline

**Components**:
```
audio_injestion.py → Whisper transcription + language detection
info_extraction.py → spaCy + Ollama NLP extraction  
eligibility_checker.py → Rule-based scheme matching
vector_db.py → Semantic scheme search
web_scraper.py → Government data updates
OllamaAgent.py → LLM integration
```

**Processing Pipeline**:
```
Voice/Text Input
├─ Audio Transcription (Whisper)
├─ Information Extraction (spaCy + Ollama)
├─ Eligibility Checking (Rules Engine)
├─ Vector Search (Semantic Matching)
└─ Response Generation (Multilingual)
```

### **4. 🏦 EFR Database (Electronic Farmer Records)**
- **Location**: `components/efr-db/`
- **Port**: 8001
- **Purpose**: Stores comprehensive farmer profiles
- **Database**: MongoDB (`agrisahayak.farmers`)

**Current Schema (Basic)**:
```python
{
  "name": str,
  "contact": str,
  "land_size": float,
  "crops": List[str],
  "location": str
}
```

**Required Schema (Enhanced)**:
```python
{
  "farmer_id": str,  # ← CRITICAL LINK
  "telegram_user_id": int,  # ← CRITICAL LINK
  "name": str,
  "contact": str,
  "land_size": float,
  "crops": List[str],
  "location": str,
  "annual_income": float,
  "irrigation_type": str,
  "land_ownership": str,
  "age": int,
  "family_size": int,
  "created_at": datetime,
  "updated_at": datetime,
  "data_source": str,
  "last_ai_processing": datetime
}
```

### **5. 📄 Form Filler (Application Generator)**
- **Location**: `components/form-filler/`
- **Port**: 8002
- **Purpose**: Auto-generates government scheme applications

**Logic**:
```python
if "rice" in farmer.crops:
    scheme = "PM-KISAN"
else:
    scheme = "Soil Health Card"
```

**Output**: JSON files with filled application data

### **6. 📊 Status Tracker (Application Management)**
- **Location**: `components/status-tracker/`
- **Port**: 8003
- **Purpose**: Tracks application submission status
- **States**: pending, submitted, approved, rejected
- **Storage**: In-memory (planned: database)

### **7. 📈 Monitoring (System Health)**
- **Location**: `components/monitoring/`
- **Port**: 8084
- **Purpose**: System health monitoring and administration

**Features**:
- Public dashboard (system status for users)
- Admin dashboard (full system control)
- Docker container management
- Service health checks
- Performance monitoring

---

## 🔄 **COMPLETE SYSTEM FLOW**

### **STEP 1: Farmer Input** 🎤
```
Farmer Opens Telegram → Types or Records Voice Message

Examples:
🗣️ "मेरे पास 2 एकड़ जमीन है, धान उगाता हूं, सरकारी योजना चाहिए"
🗣️ "I have 3 acres, grow wheat and cotton, need government help"  
🗣️ "എനിക്ക് ഒരു ഏക്കർ സ്ഥലമുണ്ട്, നെല്ലുകൃഷി ചെയ്യുന്നു"
```

### **STEP 2: Telegram Bot Processing** 📱
```
Session Flow:
1. User starts session (/start_log)
2. Bot creates session in database
3. User sends text/voice messages
4. Bot logs messages to session
5. User ends session (/end_log)
6. Bot confirms data storage has started
7. Background processing stores data in EFR via Orchestrator→AI Agent
8. Bot notifies user when storage is complete
9. User can check eligibility via /status command
```

### **STEP 3: Data Storage vs Eligibility Checking** 🔄
```
CURRENT APPROACH - TWO STAGE PROCESS:

Stage 1 - Data Storage (After /end_log):
Telegram Bot → Orchestrator → AI Agent → EFR Database
                                    ↓
                               Basic farmer data extraction
                               (No eligibility analysis yet)

Stage 2 - Eligibility Checking (When /status is called):
Telegram Bot → Direct Eligibility Check → Show Results to User
```

### **STEP 4: AI Agent Integration** 🧠
```
AI Agent will be called by Orchestrator with:

Basic Data Storage Mode:
POST /api/v1/process
{
  "session_id": "session_xyz",
  "farmer_id": "farmer_abc", 
  "content": "combined text + transcribed voice",
  "language": "hi",
  "processing_type": "data_storage"  # Only extract and store basic info
}

Response: Farmer data for EFR storage (no eligibility)

Eligibility Check Mode (future):
POST /api/v1/check_eligibility  
{
  "farmer_id": "farmer_abc",
  "language": "hi"
}

Response: Full eligibility analysis with schemes
```

### **STEP 5: Response to Farmer** 📤
```
Orchestrator → Telegram Bot → Farmer

Structured Response:
{
  "status": "completed",
  "farmer_id": "farmer_abc123",
  "eligible_schemes": [
    {
      "scheme_name": "PM-KISAN",
      "benefit": "₹6000/year",
      "eligibility_score": 0.9,
      "status": "eligible"
    },
    {
      "scheme_name": "PMFBY", 
      "benefit": "Crop Insurance",
      "eligibility_score": 0.8,
      "status": "eligible"
    }
  ],
  "recommendations": [
    "आपको PM-KISAN योजना के लिए तुरंत आवेदन करना चाहिए",
    "PMFBY फसल बीमा भी लें - बारिश का मौसम आ रहा है"
  ],
  "required_documents": [
    "आधार कार्ड",
    "बैंक खाता पासबुक", 
    "जमीन के कागजात (खतौनी)"
  ],
  "next_steps": [
    "अपने नजदीकी कृषि केंद्र में जाएं",
    "सभी कागजात की फोटोकॉपी तैयार करें"
  ],
  "applications_submitted": ["PM-KISAN", "PMFBY"]
}

Bot Formats for User:
"🎉 राम जी, आपको 2 सरकारी योजनाओं के लिए चुना गया है!

✅ PM-KISAN योजना (₹6000/वर्ष)
   स्कोर: 90% - पूर्ण पात्र

✅ PMFBY फसल बीमा  
   स्कोर: 80% - पूर्ण पात्र

📋 जरूरी कागजात:
• आधार कार्ड
• बैंक पासबुक  
• जमीन के कागजात

📝 आवेदन स्थिति:
✓ PM-KISAN - जमा हो गया
✓ PMFBY - जमा हो गया

🔍 स्थिति देखने के लिए: /status"
```

---

## 🔗 **CRITICAL: USER RECORD CORRESPONDENCE**

### **Current Problem - DISCONNECTED SYSTEMS:**

**Telegram Bot Database**:
```
sanchalak_users.farmer_verification:
{
  "farmer_id": "farmer_abc123",
  "telegram_user_id": 123456789,
  "phone": "+919876543210",
  "name": "राम शर्मा"
}
```

**EFR Database**:
```
agrisahayak.farmers:
{
  "name": "Ramesh",  ← DIFFERENT!
  "contact": "9876543210",  ← NO LINK!
  "land_size": 2.5
}
```

### **Solution - LINKED RECORDS:**

1. **Update EFR Schema** to include `farmer_id` and `telegram_user_id`
2. **Update Orchestrator** to pass linkage data
3. **Create API endpoints** for linked operations
4. **Implement data consistency** checks

### **Benefits of Proper Linkage:**
- **Single Source of Truth**: Same farmer across all systems
- **Profile Management**: Users can view complete profiles
- **Historical Tracking**: Track farming activities over time  
- **Data Analytics**: Analyze patterns and effectiveness
- **Government Integration**: Official records for applications

---

## 🚀 **CURRENT vs FUTURE STATE**

### **CURRENT (With Mocks)**:
```
Farmer Voice → Bot → Orchestrator → MOCK_AI() → Services → Response
                                     ↑
                             Random fake data
                             No real processing
                             Basic scheme matching
```

### **FUTURE (With Real AI)**:
```
Farmer Voice → Bot → Orchestrator → AI_AGENT → Services → Response
                                     ↑
                              Real Whisper transcription
                              Real spaCy + Ollama extraction
                              Real eligibility checking
                              Real vector search
                              Real multilingual processing
```

---

## 🛠️ **IMPLEMENTATION ROADMAP**

### **Phase 1: AI Agent Integration**
1. ✅ Create `components/ai-agent/` Docker service
2. ✅ Copy agent code to proper component structure
3. ✅ Create Dockerfile and requirements
4. ✅ Add to docker-compose.yml
5. ✅ Update orchestrator to call real AI APIs

### **Phase 2: User Record Correspondence**
1. ✅ Update EFR database schema
2. ✅ Add farmer_id and telegram_user_id linkage
3. ✅ Update orchestrator to pass linkage data
4. ✅ Create linked API endpoints
5. ✅ Implement data consistency validation

### **Phase 3: Enhanced Features**
1. ✅ Improve multilingual processing
2. ✅ Add more government schemes
3. ✅ Implement vector database updates
4. ✅ Add monitoring for AI Agent
5. ✅ Performance optimization

### **Phase 4: Production Readiness**
1. ✅ Security hardening
2. ✅ Performance testing
3. ✅ Error handling improvements
4. ✅ Documentation completion
5. ✅ Deployment scripts

---

## 📊 **SERVICE MAPPING**

| Service | Port | Purpose | Database | Status |
|---------|------|---------|----------|--------|
| telegram-bot | 8080 | User Interface | MongoDB (users) | ✅ Working |
| orchestrator | 8000 | Coordination | - | ✅ Working (mocked) |
| **ai-agent** | **8004** | **AI Processing** | **Vector DB** | **🚧 To Implement** |
| efr-db | 8001 | Farmer Records | MongoDB (farmers) | ✅ Working |
| form-filler | 8002 | Applications | File System | ✅ Working |
| status-tracker | 8003 | Status Management | In-Memory | ✅ Working |
| monitoring | 8084 | Health Dashboard | - | ✅ Working |
| nginx | 80/443 | Reverse Proxy | - | ✅ Working |

---

## 🔍 **KEY INTEGRATION POINTS**

### **1. Orchestrator → AI Agent**
```python
# Replace mock functions with real AI calls
response = await http_client.post(
    "http://ai-agent:8000/api/v1/process",
    json={
        "text_input": combined_text,
        "audio_files": voice_file_paths,
        "farmer_id": session_data.farmer_id,
        "language_hint": session_data.user_language
    }
)
```

### **2. AI Agent → EFR Database (via Orchestrator)**
```python
# Structured data with linkage
farmer_record = {
    "farmer_id": session_data.farmer_id,
    "telegram_user_id": session_data.telegram_user_id,
    **ai_result.farmer_info.dict()
}
```

### **3. Telegram Bot ↔ EFR Database Queries**
```python
# User profile retrieval
GET /farmer/{farmer_id}
GET /farmer/telegram/{telegram_user_id}

# Historical data
GET /farmer/{farmer_id}/sessions
GET /farmer/{farmer_id}/applications
```

---

## 🎯 **SUCCESS METRICS**

### **Technical Metrics**:
- AI processing accuracy > 90%
- Response time < 10 seconds
- System uptime > 99.5%
- Data consistency 100%

### **User Experience Metrics**:
- Farmer registration completion rate
- Session completion rate  
- Scheme application success rate
- User satisfaction scores

### **Business Metrics**:
- Number of farmers onboarded
- Government schemes accessed
- Applications submitted
- Rural digital adoption rate

---

**This document serves as the complete technical reference for the Sanchalak system architecture, implementation plan, and integration requirements.** 