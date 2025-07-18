#!/usr/bin/env python3
"""
Unified Scheme & Eligibility Service
Manages scheme definitions AND provides eligibility checking via Prolog
Eliminates all file path dependencies for production deployments
"""

import os
import json
import yaml
import logging
import tempfile
import sys
from datetime import datetime, UTC
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from starlette.exceptions import HTTPException as StarletteHTTPException

# Try to import Prolog functionality
try:
    from pyswip import Prolog
    PROLOG_AVAILABLE = True
except ImportError:
    PROLOG_AVAILABLE = False
    print("⚠️  PySWIP not available. Install with: pip install pyswip")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "scheme_backend")
COLLECTION_NAME = "schemes"

# Initialize MongoDB
client = MongoClient(MONGODB_URL)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

# API key for admin endpoints
API_KEY = os.getenv("SCHEME_API_KEY", "supersecretkey")
TRUSTED_ORIGINS = ["http://localhost", "http://127.0.0.1"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting Unified Scheme & Eligibility Service")
    
    # Test MongoDB connection
    try:
        client.admin.command('ping')
        logger.info("✅ MongoDB connection successful")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    # Check if schemes already exist in database
    global schemes_loaded, last_load_time
    existing_schemes = collection.count_documents({})
    if existing_schemes > 0:
        logger.info(f"✅ Found {existing_schemes} existing schemes in database")
        schemes_loaded = True
        # Get the last loaded time from database
        latest_scheme = collection.find_one(sort=[('_loaded_at', -1)])
        if latest_scheme and '_loaded_at' in latest_scheme:
            last_load_time = latest_scheme['_loaded_at']
    else:
        logger.info("ℹ️ No schemes found in database. Upload YAML files via /upload endpoint.")
    
    # Check Prolog availability
    if PROLOG_AVAILABLE:
        logger.info("✅ Prolog engine available for eligibility checking")
    else:
        logger.warning("⚠️ Prolog engine not available - eligibility checking disabled")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Unified Scheme & Eligibility Service")
    
    # Clean up Prolog engines
    for engine in prolog_engines.values():
        engine.cleanup()
    
    client.close()

# FastAPI app
app = FastAPI(
    title="Unified Scheme & Eligibility Service",
    description="Manages government scheme definitions and provides eligibility checking",
    version="1.0.0",
    lifespan=lifespan
)

# Restrict CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=TRUSTED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Secure headers middleware
class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
app.add_middleware(SecureHeadersMiddleware)

def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

# Pydantic models
class SchemeInfo(BaseModel):
    """Response model for scheme information"""
    scheme_id: str
    name: str
    description: str
    category: str
    ministry: str
    upload_date: str
    file_size: int
    version: str = "1.0"

class EligibilityRequest(BaseModel):
    """Request model for eligibility checking"""
    scheme_id: str
    farmer_data: Dict[str, Any]
    farmer_id: Optional[str] = None

class EligibilityResponse(BaseModel):
    """Response model for eligibility checking"""
    scheme_id: str
    farmer_id: Optional[str]
    is_eligible: bool
    explanation: str
    confidence_score: float
    details: Dict[str, Any]
    timestamp: str

# Additional Pydantic models for updated functionality
class SchemeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SchemeListResponse(BaseModel):
    success: bool
    message: str
    data: Dict[str, Any]
    error: Optional[str] = None

class SchemeLoadRequest(BaseModel):
    yaml_content: Optional[str] = None
    force_reload: bool = False

# Global variables for compatibility
schemes_loaded = False
last_load_time = None

# Global scheme cache and Prolog engines
scheme_cache = {}
prolog_engines = {}

# Prolog Eligibility Engine
class PrologEligibilityEngine:
    """Unified Prolog engine for eligibility checking across multiple schemes"""
    
    def __init__(self, scheme_id: str, prolog_rules: str):
        self.scheme_id = scheme_id
        self.prolog_rules = prolog_rules
        self.prolog = None
        self.temp_file = None
        
        if PROLOG_AVAILABLE:
            self._initialize_prolog()
    
    def _initialize_prolog(self):
        """Initialize Prolog engine with scheme-specific rules"""
        try:
            # Create temporary file for Prolog rules
            self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pl', delete=False)
            self.temp_file.write(self.prolog_rules)
            self.temp_file.flush()
            
            # Initialize Prolog engine
            self.prolog = Prolog()
            self.prolog.consult(self.temp_file.name)
            
            logger.info(f"✅ Prolog engine initialized for scheme: {self.scheme_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Prolog for {self.scheme_id}: {str(e)}")
            raise
    
    def convert_to_prolog_facts(self, farmer_data: Dict[str, Any]) -> List[str]:
        """Convert farmer data to Prolog facts"""
        facts = []
        
        # Basic farmer info
        farmer_id = farmer_data.get("farmer_id", farmer_data.get("aadhaar_number", "unknown"))
        facts.append(f"farmer_id({farmer_id}).")
        
        # Personal details
        if "name" in farmer_data:
            facts.append(f"farmer_name({farmer_id}, '{farmer_data['name']}').")
        if "age" in farmer_data:
            facts.append(f"farmer_age({farmer_id}, {farmer_data['age']}).")
        if "gender" in farmer_data:
            facts.append(f"farmer_gender({farmer_id}, '{farmer_data['gender']}').")
        
        # Location details
        if "state" in farmer_data:
            facts.append(f"farmer_state({farmer_id}, '{farmer_data['state']}').")
        if "district" in farmer_data:
            facts.append(f"farmer_district({farmer_id}, '{farmer_data['district']}').")
        if "village" in farmer_data:
            facts.append(f"farmer_village({farmer_id}, '{farmer_data['village']}').")
        
        # Land details
        if "land_size_acres" in farmer_data:
            facts.append(f"land_size({farmer_id}, {farmer_data['land_size_acres']}).")
        if "land_ownership" in farmer_data:
            facts.append(f"land_ownership({farmer_id}, '{farmer_data['land_ownership']}').")
        
        # Financial details
        if "annual_income" in farmer_data:
            facts.append(f"annual_income({farmer_id}, {farmer_data['annual_income']}).")
        if "bank_account" in farmer_data:
            facts.append(f"has_bank_account({farmer_id}, {str(farmer_data['bank_account']).lower()}).")
        if "aadhaar_linked" in farmer_data:
            facts.append(f"aadhaar_linked({farmer_id}, {str(farmer_data['aadhaar_linked']).lower()}).")
        
        # Category and region
        if "category" in farmer_data:
            facts.append(f"farmer_category({farmer_id}, '{farmer_data['category']}').")
        if "region" in farmer_data:
            facts.append(f"farmer_region({farmer_id}, '{farmer_data['region']}').")
        
        # Exclusion criteria
        exclusion_fields = [
            'is_constitutional_post_holder', 'is_political_office_holder', 
            'is_government_employee', 'is_income_tax_payer', 
            'is_professional', 'is_nri', 'is_pensioner'
        ]
        
        for field in exclusion_fields:
            if field in farmer_data:
                facts.append(f"{field}({farmer_id}, {str(farmer_data[field]).lower()}).")
        
        return facts
    
    def check_eligibility(self, farmer_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Check eligibility using Prolog rules"""
        if not PROLOG_AVAILABLE:
            return False, "Prolog not available", {}
        
        try:
            # Convert farmer data to Prolog facts
            facts = self.convert_to_prolog_facts(farmer_data)
            farmer_id = farmer_data.get("farmer_id", farmer_data.get("aadhaar_number", "unknown"))
            
            # Add facts to Prolog engine
            for fact in facts:
                try:
                    self.prolog.assertz(fact)
                except Exception as e:
                    logger.warning(f"Failed to add fact: {fact} - {str(e)}")
            
            # Query eligibility
            query = f"eligible({farmer_id})"
            results = list(self.prolog.query(query))
            
            is_eligible = len(results) > 0
            
            # Get explanation
            explanation = self._get_explanation(farmer_id, is_eligible)
            
            # Get detailed analysis
            details = self._get_detailed_analysis(farmer_id)
            
            return is_eligible, explanation, details
            
        except Exception as e:
            logger.error(f"Error checking eligibility: {str(e)}")
            return False, f"Error during eligibility check: {str(e)}", {}
    
    def _get_explanation(self, farmer_id: str, is_eligible: bool) -> str:
        """Generate explanation for eligibility decision"""
        try:
            if is_eligible:
                return f"Farmer {farmer_id} is eligible for the {self.scheme_id} scheme based on the provided information."
            else:
                # Try to find specific reasons for ineligibility
                exclusion_queries = [
                    f"is_constitutional_post_holder({farmer_id}, true)",
                    f"is_government_employee({farmer_id}, true)",
                    f"is_income_tax_payer({farmer_id}, true)",
                    f"is_professional({farmer_id}, true)",
                    f"is_nri({farmer_id}, true)"
                ]
                
                exclusion_reasons = []
                for query in exclusion_queries:
                    try:
                        if list(self.prolog.query(query)):
                            exclusion_reasons.append(query.split('(')[0].replace('_', ' ').title())
                    except:
                        pass
                
                if exclusion_reasons:
                    reasons = ", ".join(exclusion_reasons)
                    return f"Farmer {farmer_id} is not eligible due to: {reasons}"
                else:
                    return f"Farmer {farmer_id} does not meet the eligibility criteria for the {self.scheme_id} scheme."
        except:
            return f"Unable to generate detailed explanation for farmer {farmer_id}."
    
    def _get_detailed_analysis(self, farmer_id: str) -> Dict[str, Any]:
        """Get detailed analysis of eligibility factors"""
        details = {
            "farmer_id": farmer_id,
            "scheme_id": self.scheme_id,
            "criteria_met": [],
            "criteria_failed": [],
            "exclusion_factors": []
        }
        
        try:
            # Check various criteria
            criteria_checks = [
                ("has_bank_account", f"has_bank_account({farmer_id}, true)"),
                ("aadhaar_linked", f"aadhaar_linked({farmer_id}, true)"),
                ("valid_land_ownership", f"land_ownership({farmer_id}, _)"),
                ("valid_age", f"farmer_age({farmer_id}, Age), Age >= 18"),
            ]
            
            for criterion, query in criteria_checks:
                try:
                    if list(self.prolog.query(query)):
                        details["criteria_met"].append(criterion)
                    else:
                        details["criteria_failed"].append(criterion)
                except:
                    details["criteria_failed"].append(criterion)
            
        except Exception as e:
            logger.error(f"Error in detailed analysis: {str(e)}")
        
        return details
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_file:
            try:
                os.unlink(self.temp_file.name)
            except:
                pass

# Utility functions
def get_scheme_from_db(scheme_id: str) -> Optional[Dict[str, Any]]:
    """Get scheme from database"""
    try:
        scheme = collection.find_one({"scheme_id": scheme_id})
        return scheme
    except Exception as e:
        logger.error(f"Error retrieving scheme {scheme_id}: {str(e)}")
        return None

def get_prolog_engine(scheme_id: str) -> Optional[PrologEligibilityEngine]:
    """Get or create Prolog engine for a scheme"""
    if scheme_id in prolog_engines:
        return prolog_engines[scheme_id]
    
    # Load scheme from database
    scheme = get_scheme_from_db(scheme_id)
    if not scheme:
        return None
    
    # Extract Prolog rules from scheme
    prolog_rules = scheme.get("prolog_rules", "")
    if not prolog_rules:
        logger.warning(f"No Prolog rules found for scheme {scheme_id}")
        return None
    
    try:
        # Create and cache Prolog engine
        engine = PrologEligibilityEngine(scheme_id, prolog_rules)
        prolog_engines[scheme_id] = engine
        return engine
    except Exception as e:
        logger.error(f"Failed to create Prolog engine for {scheme_id}: {str(e)}")
        return None

def load_yaml_to_mongodb(yaml_content: str) -> bool:
    """Load YAML scheme definition into MongoDB with Prolog rules extraction"""
    global schemes_loaded, last_load_time
    
    try:
        # Parse YAML content
        data = yaml.safe_load(yaml_content)
        
        if not data:
            logger.error("Invalid YAML content")
            return False
        
        # Clear existing schemes
        collection.delete_many({})
        
        # Handle different YAML structures
        schemes_to_process = []
        
        if 'schemes' in data:
            # Multiple schemes format
            schemes_to_process = data['schemes']
        elif 'scheme' in data:
            # Single scheme format
            schemes_to_process = [data['scheme']]
        else:
            # Direct scheme format
            schemes_to_process = [data]
        
        # Insert each scheme
        schemes_inserted = 0
        for scheme_data in schemes_to_process:
            # Generate scheme_id if not present
            if 'scheme_id' not in scheme_data:
                scheme_data['scheme_id'] = scheme_data.get('code', f"scheme_{schemes_inserted}")
            
            # Extract Prolog rules from various possible locations
            prolog_rules = ""
            
            # Check for Prolog rules in different locations
            if 'prolog_rules' in scheme_data:
                prolog_rules = scheme_data['prolog_rules']
            elif 'eligibility_rules' in scheme_data:
                # Try to extract from eligibility_rules if it's a string
                rules = scheme_data['eligibility_rules']
                if isinstance(rules, str) and ('eligible(' in rules or ':-' in rules):
                    prolog_rules = rules
                elif isinstance(rules, dict) and 'prolog_code' in rules:
                    prolog_rules = rules['prolog_code']
            
            # If no Prolog rules found, try to generate basic ones
            if not prolog_rules:
                prolog_rules = generate_basic_prolog_rules(scheme_data)
            
            # Store the Prolog rules in the scheme
            scheme_data['prolog_rules'] = prolog_rules
            
            # Add metadata
            scheme_data['_loaded_at'] = datetime.now(UTC)
            scheme_data['_version'] = "1.0"
            scheme_data['_original_yaml'] = yaml_content
            
            # Insert into MongoDB
            result = collection.insert_one(scheme_data)
            if result.inserted_id:
                schemes_inserted += 1
                logger.info(f"Inserted scheme: {scheme_data.get('scheme_id', 'Unknown')}")
        
        # Create indexes for better performance
        collection.create_index("scheme_id", unique=True)
        collection.create_index("code")
        collection.create_index("name")
        collection.create_index("ministry")
        
        schemes_loaded = True
        last_load_time = datetime.now(UTC)
        logger.info(f"Successfully loaded {schemes_inserted} schemes into MongoDB")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load YAML to MongoDB: {e}")
        return False

def generate_basic_prolog_rules(scheme_data: Dict[str, Any]) -> str:
    """Generate basic Prolog rules if none are provided"""
    scheme_id = scheme_data.get('scheme_id', 'unknown')
    
    # Basic rule template
    prolog_rules = f"""
% Basic eligibility rules for {scheme_id}
% Generated automatically - customize as needed

% Basic eligibility predicate
eligible(FarmerId) :-
    farmer_id(FarmerId),
    basic_eligibility_check(FarmerId).

% Basic eligibility requirements
basic_eligibility_check(FarmerId) :-
    farmer_age(FarmerId, Age),
    Age >= 18,
    has_bank_account(FarmerId, true),
    not_excluded(FarmerId).

% Exclusion criteria
not_excluded(FarmerId) :-
    \\+ is_government_employee(FarmerId, true),
    \\+ is_income_tax_payer(FarmerId, true),
    \\+ is_constitutional_post_holder(FarmerId, true).

% Default facts if not provided
has_bank_account(FarmerId, true) :- 
    farmer_id(FarmerId),
    \\+ has_bank_account(FarmerId, false).

% Age validation
valid_age(FarmerId) :-
    farmer_age(FarmerId, Age),
    Age >= 18,
    Age =< 100.
"""
    
    return prolog_rules.strip()

# Startup and shutdown events are now handled by the lifespan context manager above

# API Endpoints

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "detail": "📜 Whoops! This scheme server endpoint doesn’t exist. Check your path or see /docs for available APIs!",
            "path": str(request.url)
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "schemes_loaded": schemes_loaded,
        "last_load_time": last_load_time.isoformat() if last_load_time else None,
        "total_schemes": collection.count_documents({}),
        "timestamp": datetime.now(UTC).isoformat()
    }

@app.get("/schemes", response_model=SchemeListResponse)
async def list_schemes():
    """List all schemes with only scheme_id and name"""
    try:
        schemes = list(collection.find({}, {"_id": 0, "scheme_id": 1, "name": 1}))
        return SchemeListResponse(
            success=True,
            message=f"Retrieved {len(schemes)} schemes",
            data={"schemes": schemes},
            error=None
        )
    except Exception as e:
        logger.error(f"Failed to list schemes: {e}")
        return SchemeListResponse(
            success=False,
            message="Failed to list schemes",
            data={},
            error=str(e)
        )

@app.get("/schemes/{scheme_code}", response_model=SchemeResponse)
async def get_scheme(scheme_code: str):
    """Get a specific scheme by code"""
    try:
        scheme = collection.find_one({"code": scheme_code.upper()}, {"_id": 0})
        
        if not scheme:
            raise HTTPException(status_code=404, detail=f"Scheme '{scheme_code}' not found")
        
        return SchemeResponse(
            success=True,
            message=f"Retrieved scheme {scheme_code}",
            data=scheme
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving scheme {scheme_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve scheme: {str(e)}")

@app.get("/schemes/{scheme_code}/fields")
async def get_scheme_fields(scheme_code: str):
    """Get all fields for a specific scheme"""
    try:
        scheme = collection.find_one({"code": scheme_code.upper()}, {"_id": 0})
        
        if not scheme:
            raise HTTPException(status_code=404, detail=f"Scheme '{scheme_code}' not found")
        
        # Extract all fields from data_model
        fields = {}
        data_model = scheme.get("data_model", {})
        
        for section_name, section_data in data_model.items():
            if isinstance(section_data, dict):
                for field_name, field_def in section_data.items():
                    if isinstance(field_def, dict):
                        fields[field_name] = field_def
        
        return SchemeResponse(
            success=True,
            message=f"Retrieved fields for scheme {scheme_code}",
            data={
                "scheme_code": scheme_code,
                "fields": fields,
                "total_fields": len(fields)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving fields for scheme {scheme_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve scheme fields: {str(e)}")

@app.post("/upload", response_model=SchemeResponse)
async def upload_yaml_file(file: UploadFile = File(...), request: Request = None):
    verify_api_key(request)
    try:
        # Validate file type
        if not file.filename.endswith(('.yaml', '.yml')):
            raise HTTPException(
                status_code=400, 
                detail="Only YAML files (.yaml, .yml) are supported"
            )
        
        # Read file content
        content = await file.read()
        yaml_content = content.decode('utf-8')
        
        # Load into MongoDB
        success = load_yaml_to_mongodb(yaml_content)
        
        if success:
            total_schemes = collection.count_documents({})
            return SchemeResponse(
                success=True,
                message=f"Successfully uploaded and loaded {total_schemes} schemes from {file.filename}",
                data={
                    "filename": file.filename,
                    "total_schemes": total_schemes,
                    "loaded_at": last_load_time.isoformat() if last_load_time else None
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to process uploaded YAML file")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@app.post("/schemes/reload", response_model=SchemeResponse)
async def reload_schemes(request: SchemeLoadRequest, req: Request = None):
    verify_api_key(req)
    try:
        if not request.yaml_content:
            raise HTTPException(status_code=400, detail="YAML content is required")
        
        success = load_yaml_to_mongodb(request.yaml_content)
        
        if success:
            total_schemes = collection.count_documents({})
            return SchemeResponse(
                success=True,
                message=f"Successfully reloaded {total_schemes} schemes",
                data={
                    "total_schemes": total_schemes,
                    "loaded_at": last_load_time.isoformat() if last_load_time else None
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to reload schemes from YAML")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading schemes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload schemes: {str(e)}")

@app.delete("/schemes/clear", response_model=SchemeResponse)
async def clear_all_schemes(request: Request = None):
    verify_api_key(request)
    """Clear all schemes from the database"""
    try:
        global schemes_loaded, last_load_time
        
        result = collection.delete_many({})
        schemes_loaded = False
        last_load_time = None
        
        return SchemeResponse(
            success=True,
            message=f"Successfully cleared {result.deleted_count} schemes from database",
            data={"cleared_count": result.deleted_count}
        )
        
    except Exception as e:
        logger.error(f"Error clearing schemes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear schemes: {str(e)}")

@app.get("/openapi.json")
async def openapi_schema():
    return get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description=app.description
    )

@app.get("/")
async def service_info():
    """Service information and available endpoints"""
    return {
        "service": "Unified Scheme & Eligibility Service",
        "version": app.version,
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": {
            "swagger_ui": "/docs",
            "openapi_json": "/openapi.json"
        }
    }

@app.get("/schemes/{scheme_code}/eligibility-rules")
async def get_eligibility_rules(scheme_code: str):
    """Get eligibility rules for a specific scheme"""
    try:
        scheme = collection.find_one({"code": scheme_code.upper()}, {"_id": 0})
        
        if not scheme:
            raise HTTPException(status_code=404, detail=f"Scheme '{scheme_code}' not found")
        
        # Extract eligibility rules
        eligibility_rules = scheme.get("eligibility_rules", {})
        
        return SchemeResponse(
            success=True,
            message=f"Retrieved eligibility rules for scheme {scheme_code}",
            data={
                "scheme_code": scheme_code,
                "eligibility_rules": eligibility_rules
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving eligibility rules for scheme {scheme_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve eligibility rules: {str(e)}")

@app.get("/schemes/{scheme_code}/conversation-config")
async def get_conversation_config(scheme_code: str):
    """Get conversation configuration for a specific scheme"""
    try:
        scheme = collection.find_one({"code": scheme_code.upper()}, {"_id": 0})
        
        if not scheme:
            raise HTTPException(status_code=404, detail=f"Scheme '{scheme_code}' not found")
        
        # Extract conversation configuration
        conversation_config = scheme.get("conversation_config", {})
        extraction_prompts = scheme.get("extraction_prompts", {})
        
        return SchemeResponse(
            success=True,
            message=f"Retrieved conversation config for scheme {scheme_code}",
            data={
                "scheme_code": scheme_code,
                "conversation_config": conversation_config,
                "extraction_prompts": extraction_prompts
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation config for scheme {scheme_code}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conversation config: {str(e)}")

# NEW ELIGIBILITY CHECKING ENDPOINTS

@app.post("/eligibility/check", response_model=Dict[str, Any])
async def check_eligibility(request: EligibilityRequest):
    """Check eligibility for a specific scheme using Prolog rules"""
    try:
        if not PROLOG_AVAILABLE:
            raise HTTPException(
                status_code=503, 
                detail="Prolog engine not available. Install pyswip to enable eligibility checking."
            )
        
        # Get Prolog engine for the scheme
        engine = get_prolog_engine(request.scheme_id)
        if not engine:
            raise HTTPException(
                status_code=404, 
                detail=f"Scheme '{request.scheme_id}' not found or has no Prolog rules"
            )
        
        # Check eligibility
        is_eligible, explanation, details = engine.check_eligibility(request.farmer_data)
        
        return {
            "success": True,
            "scheme_id": request.scheme_id,
            "farmer_id": request.farmer_id,
            "is_eligible": is_eligible,
            "explanation": explanation,
            "confidence_score": 0.95 if is_eligible else 0.85,
            "details": details,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking eligibility: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check eligibility: {str(e)}")

@app.get("/eligibility/schemes")
async def list_eligibility_schemes():
    """List all schemes that support eligibility checking"""
    try:
        # Find schemes with Prolog rules
        schemes = list(collection.find(
            {"prolog_rules": {"$exists": True, "$ne": ""}},
            {"_id": 0, "scheme_id": 1, "name": 1, "description": 1, "category": 1}
        ))
        
        return {
            "success": True,
            "message": f"Found {len(schemes)} schemes with eligibility checking",
            "schemes": schemes,
            "total_count": len(schemes)
        }
        
    except Exception as e:
        logger.error(f"Error listing eligibility schemes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list eligibility schemes: {str(e)}")

@app.get("/eligibility/schemes/{scheme_id}/rules")
async def get_prolog_rules(scheme_id: str):
    """Get Prolog rules for a specific scheme"""
    try:
        scheme = get_scheme_from_db(scheme_id)
        if not scheme:
            raise HTTPException(status_code=404, detail=f"Scheme '{scheme_id}' not found")
        
        prolog_rules = scheme.get("prolog_rules", "")
        if not prolog_rules:
            raise HTTPException(status_code=404, detail=f"No Prolog rules found for scheme '{scheme_id}'")
        
        return {
            "success": True,
            "scheme_id": scheme_id,
            "prolog_rules": prolog_rules,
            "rules_length": len(prolog_rules)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving Prolog rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve Prolog rules: {str(e)}")

@app.post("/eligibility/batch")
async def batch_eligibility_check(requests: List[EligibilityRequest]):
    """Check eligibility for multiple farmers across different schemes"""
    try:
        if not PROLOG_AVAILABLE:
            raise HTTPException(
                status_code=503, 
                detail="Prolog engine not available. Install pyswip to enable eligibility checking."
            )
        
        results = []
        
        for request in requests:
            try:
                engine = get_prolog_engine(request.scheme_id)
                if engine:
                    is_eligible, explanation, details = engine.check_eligibility(request.farmer_data)
                    
                    results.append({
                        "scheme_id": request.scheme_id,
                        "farmer_id": request.farmer_id,
                        "is_eligible": is_eligible,
                        "explanation": explanation,
                        "details": details,
                        "success": True
                    })
                else:
                    results.append({
                        "scheme_id": request.scheme_id,
                        "farmer_id": request.farmer_id,
                        "is_eligible": False,
                        "explanation": f"Scheme '{request.scheme_id}' not found or has no Prolog rules",
                        "details": {},
                        "success": False
                    })
                    
            except Exception as e:
                results.append({
                    "scheme_id": request.scheme_id,
                    "farmer_id": request.farmer_id,
                    "is_eligible": False,
                    "explanation": f"Error checking eligibility: {str(e)}",
                    "details": {},
                    "success": False
                })
        
        return {
            "success": True,
            "message": f"Processed {len(results)} eligibility requests",
            "results": results,
            "timestamp": datetime.now(UTC).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch eligibility check: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process batch eligibility check: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=False) 