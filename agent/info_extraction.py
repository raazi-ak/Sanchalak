"""
Enhanced Information Extraction Agent (NLU) with Ollama LLM Integration
Extracts farmer information using spaCy, rule-based patterns, NER, and Ollama for adaptive extraction
"""

import re
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
import spacy
from spacy.matcher import Matcher, PhraseMatcher
import json
import os
# Add these imports
from app.agents.eligibility_checker import EligibilityCheckerAgent
from app.agents.vector_db import VectorDBAgent
from app.agents.web_scraper import WebScraperAgent
from app.agents.ollama import OllamaAgent
# Ollama integration imports
try:
    import ollama
    from ollama import Client, ChatResponse
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from app.config import get_settings
from app.models import ExtractedInfo, FarmerInfo, LanguageCode
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class EnhancedInfoExtractionAgent:
    """Enhanced Agent for extracting farmer information with Ollama LLM integration"""
    
    def __init__(self):
        self.nlp_models = {}
        self.ollama_client = None
        self.matchers = {}
        self.agricultural_patterns = {}
        self.location_patterns = {}
        self.numeric_patterns = {}
        self.ollama_enabled = OLLAMA_AVAILABLE
        self.ollama_model = "llama3.2"  # Default model
        
    async def initialize(self):
        """Initialize spaCy models, Ollama integration, and extraction patterns"""
        try:
            logger.info("Initializing Enhanced NLU models and patterns...")
            
            # Load spaCy models
            await self._load_nlp_models()
            
            # Initialize Ollama integration if available
            if self.ollama_enabled:
                await self._initialize_ollama()
            
            # Initialize matchers and patterns
            await self._initialize_patterns()
            
            logger.info("Enhanced NLU agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced NLU agent: {str(e)}")
            raise
    
    async def _initialize_ollama(self):
        """Initialize Ollama client and check available models"""
        try:
            # Initialize Ollama client
            ollama_host = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
            self.ollama_client = Client(host=ollama_host)
            
            # Check if Ollama server is running
            try:
                models = await asyncio.get_event_loop().run_in_executor(
                    None, self.ollama_client.list
                )
                available_models = [model['name'] for model in models['models']]
                logger.info(f"Available Ollama models: {available_models}")
                
                # Set preferred model if available
                preferred_models = ['llama3.2', 'llama3.1', 'llama2', 'mistral', 'gemma2']
                for model in preferred_models:
                    if any(model in available_model for available_model in available_models):
                        self.ollama_model = model
                        logger.info(f"Using Ollama model: {self.ollama_model}")
                        break
                
                if not available_models:
                    logger.warning("No Ollama models found. Please pull a model first.")
                    self.ollama_enabled = False
                    
            except Exception as e:
                logger.warning(f"Ollama server not accessible: {str(e)}")
                self.ollama_enabled = False
                
        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {str(e)}")
            self.ollama_enabled = False
    
    async def _load_nlp_models(self):
        """Load spaCy models for different languages"""
        try:
            loop = asyncio.get_event_loop()
            
            # Load English model
            try:
                self.nlp_models['en'] = await loop.run_in_executor(
                    None, spacy.load, "en_core_web_sm"
                )
                logger.info("English spaCy model loaded")
            except OSError:
                logger.warning("English spaCy model not found, using blank model")
                self.nlp_models['en'] = spacy.blank("en")
            
            # Load models for Indian languages
            for lang in ['hi', 'gu', 'pa', 'bn', 'te', 'ta', 'ml', 'kn', 'or']:
                self.nlp_models[lang] = spacy.blank(lang)
                logger.info(f"Loaded blank model for {lang}")
            
        except Exception as e:
            logger.error(f"Failed to load NLP models: {str(e)}")
            raise
    
    async def _initialize_patterns(self):
        """Initialize extraction patterns for different entity types"""
        
        # Enhanced agricultural patterns with more comprehensive coverage
        self.agricultural_patterns = {
            'crops': [
                # Hindi crops
                'धान', 'चावल', 'गेहूं', 'मक्का', 'ज्वार', 'बाजरा', 'रागी', 'दाल', 'अरहर', 'चना',
                'मटर', 'मसूर', 'उड़द', 'मूंग', 'सरसों', 'सूरजमुखी', 'तिल', 'अलसी', 'कपास',
                'गन्ना', 'आलू', 'प्याज', 'टमाटर', 'बैंगन', 'भिंडी', 'खीरा', 'लौकी', 'करेला',
                'पत्तागोभी', 'फूलगोभी', 'गाजर', 'मूली', 'पालक', 'मेथी', 'धनिया',
                # English crops
                'rice', 'wheat', 'maize', 'corn', 'jowar', 'bajra', 'ragi', 'dal', 'arhar',
                'chickpea', 'pea', 'lentil', 'urad', 'moong', 'mustard', 'sunflower', 'sesame',
                'cotton', 'sugarcane', 'potato', 'onion', 'tomato', 'brinjal', 'okra', 'cucumber',
                'bitter gourd', 'cabbage', 'cauliflower', 'carrot', 'radish', 'spinach', 'fenugreek'
            ],
            'farming_equipment': [
                'ट्रैक्टर', 'हल', 'बीज ड्रिल', 'थ्रेशर', 'कंबाइन हार्वेस्टर', 'कल्टिवेटर',
                'tractor', 'plough', 'seed drill', 'thresher', 'combine harvester',
                'cultivator', 'harrow', 'rotavator', 'sprayer', 'weeder', 'transplanter'
            ],
            'irrigation_types': [
                'बारिश', 'नहर', 'बोरवेल', 'कुआं', 'ड्रिप सिंचाई', 'फव्वारा सिंचाई', 'नलकूप',
                'rain fed', 'canal', 'borewell', 'well', 'drip irrigation', 'sprinkler irrigation',
                'tube well', 'surface irrigation', 'flood irrigation'
            ],
            'fertilizers': [
                'खाद', 'यूरिया', 'डीएपी', 'पोटाश', 'जैविक खाद', 'कंपोस्ट', 'गोबर की खाद',
                'fertilizer', 'urea', 'dap', 'potash', 'organic manure', 'compost', 'vermicompost',
                'npk', 'phosphorus', 'nitrogen', 'potassium'
            ]
        }
        
        # Enhanced location patterns
        self.location_patterns = {
            'states': [
                'उत्तर प्रदेश', 'महाराष्ट्र', 'बिहार', 'पश्चिम बंगाल', 'मध्य प्रदेश',
                'तमिलनाडु', 'राजस्थान', 'कर्नाटक', 'गुजरात', 'आंध्र प्रदेश',
                'uttar pradesh', 'up', 'maharashtra', 'bihar', 'west bengal', 'wb',
                'madhya pradesh', 'mp', 'tamil nadu', 'tn', 'rajasthan', 'karnataka',
                'gujarat', 'andhra pradesh', 'ap', 'punjab', 'haryana', 'kerala',
                'odisha', 'jharkhand', 'chhattisgarh', 'assam', 'telangana'
            ],
            'districts': [
                'अलीगढ़', 'मेरठ', 'मुजफ्फरनगर', 'सहारनपुर', 'गाज़ियाबाद', 'आगरा', 'कानपुर',
                'aligarh', 'meerut', 'muzaffarnagar', 'saharanpur', 'ghaziabad', 'agra', 'kanpur',
                'pune', 'nashik', 'ahmednagar', 'solapur', 'sangli', 'kolhapur', 'satara'
            ]
        }
        
        # Enhanced numeric patterns
        self.numeric_patterns = {
            'land_size': [
                r'(\d+(?:\.\d+)?)\s*(?:एकड़|acre|acres|hectare|hectares|हेक्टेयर)',
                r'(\d+(?:\.\d+)?)\s*(?:बीघा|bigha)',
                r'(\d+(?:\.\d+)?)\s*(?:कट्ठा|katha)',
                r'(\d+(?:\.\d+)?)\s*(?:गुंठा|guntha)'
            ],
            'income': [
                r'(?:रुपये|रु|rs|₹|rupees?)\s*(\d+(?:,\d+)*(?:\.\d+)?)',
                r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:रुपये|रु|rs|₹|rupees?)',
                r'(\d+(?:,\d+)*)\s*(?:लाख|lakh|lakhs)',
                r'(\d+(?:,\d+)*)\s*(?:करोड़|crore|crores)'
            ],
            'age': [
                r'(\d+)\s*(?:साल|वर्ष|years?|year old)',
                r'(?:उम्र|age|आयु)\s*(\d+)'
            ],
            'family_size': [
                r'(\d+)\s*(?:सदस्य|members?|लोग|people)',
                r'(?:परिवार में|family of)\s*(\d+)'
            ]
        }
        
        # Initialize matchers for each language
        for lang_code, nlp in self.nlp_models.items():
            self.matchers[lang_code] = Matcher(nlp.vocab)
            self._add_patterns_to_matcher(lang_code)
    
    def _add_patterns_to_matcher(self, lang_code: str):
        """Add extraction patterns to spaCy matcher"""
        matcher = self.matchers[lang_code]
        
        # Crop patterns
        crop_patterns = []
        for crop in self.agricultural_patterns['crops']:
            crop_patterns.append([{"LOWER": crop.lower()}])
        
        if crop_patterns:
            matcher.add("CROPS", crop_patterns)
        
        # Location patterns
        location_patterns = []
        for location in self.location_patterns['states'] + self.location_patterns['districts']:
            location_patterns.append([{"LOWER": location.lower()}])
        
        if location_patterns:
            matcher.add("LOCATIONS", location_patterns)
        
        logger.info(f"Added patterns to matcher for {lang_code}")
    
    async def extract_information(
        self, 
        text: str, 
        language: LanguageCode = LanguageCode.HINDI
    ) -> ExtractedInfo:
        """
        Extract farmer information from text using multiple methods including Ollama LLM
        
        Args:
            text: Input text (transcribed or direct)
            language: Language of the text
            
        Returns:
            ExtractedInfo object with extracted farmer information
        """
        start_time = time.time()
        
        try:
            logger.info(f"Extracting information from text (lang: {language.value})")
            
            # Clean and preprocess text
            cleaned_text = self._preprocess_text(text)
            
            # Get appropriate NLP model
            nlp = self.nlp_models.get(language.value, self.nlp_models['en'])
            
            # Process text with spaCy
            doc = nlp(cleaned_text)
            
            # Extract entities using different methods
            entities = {}
            confidence_scores = {}
            
            # Method 1: Pattern-based extraction
            pattern_entities, pattern_confidence = await self._extract_with_patterns(
                cleaned_text, language.value
            )
            entities.update(pattern_entities)
            confidence_scores.update(pattern_confidence)
            
            # Method 2: Rule-based extraction
            rule_entities, rule_confidence = await self._extract_with_rules(
                cleaned_text, doc
            )
            entities.update(rule_entities)
            confidence_scores.update(rule_confidence)
            
            # Method 3: Named Entity Recognition (for English)
            if language == LanguageCode.ENGLISH:
                ner_entities, ner_confidence = await self._extract_with_ner(doc)
                entities.update(ner_entities)
                confidence_scores.update(ner_confidence)
            
            # Method 4: Ollama LLM-based extraction (adaptive and context-aware)
            if self.ollama_enabled:
                llm_entities, llm_confidence = await self._extract_with_ollama(
                    cleaned_text, language
                )
                # Merge LLM results with higher confidence for missing entities
                for key, value in llm_entities.items():
                    if key not in entities or confidence_scores.get(key, 0) < llm_confidence.get(key, 0):
                        entities[key] = value
                        confidence_scores[key] = llm_confidence[key]
            
            # Build FarmerInfo object
            farmer_info = self._build_farmer_info(entities)
            
            processing_time = time.time() - start_time
            
            extraction_method = "spacy+rules+patterns"
            if self.ollama_enabled:
                extraction_method += "+ollama"
            
            logger.info(f"Information extraction completed in {processing_time:.2f}s")
            
            return ExtractedInfo(
                raw_text=text,
                farmer_info=farmer_info,
                entities=entities,
                confidence_scores=confidence_scores,
                extraction_method=extraction_method
            )
            
        except Exception as e:
            logger.error(f"Information extraction failed: {str(e)}")
            
            # Return basic structure with original text
            return ExtractedInfo(
                raw_text=text,
                farmer_info=FarmerInfo(),
                entities={},
                confidence_scores={},
                extraction_method="failed"
            )
    
    async def _extract_with_ollama(
        self, text: str, language: LanguageCode
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Extract entities using Ollama LLM for adaptive and context-aware extraction"""
        entities = {}
        confidence_scores = {}
        
        if not self.ollama_enabled or not self.ollama_client:
            return entities, confidence_scores
        
        try:
            # Create structured prompt for farmer information extraction
            extraction_prompt = self._create_extraction_prompt(text, language)
            
            # Get response from Ollama
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.ollama_client.chat(
                    model=self.ollama_model,
                    messages=[{
                        'role': 'user',
                        'content': extraction_prompt
                    }],
                    options={
                        'temperature': 0.1,  # Low temperature for consistent extraction
                        'top_p': 0.9,
                        'num_predict': 500
                    }
                )
            )
            
            # Parse the LLM response
            llm_output = response['message']['content']
            parsed_entities = self._parse_ollama_response(llm_output)
            
            # Add confidence scores for LLM-extracted entities
            for key, value in parsed_entities.items():
                if value:  # Only add non-empty values
                    entities[key] = value
                    confidence_scores[key] = 0.85  # High confidence for LLM extraction
            
            logger.info(f"Ollama extracted {len(entities)} entities")
            
        except Exception as e:
            logger.warning(f"Ollama extraction failed: {str(e)}")
        
        return entities, confidence_scores
    
    def _create_extraction_prompt(self, text: str, language: LanguageCode) -> str:
        """Create a structured prompt for Ollama to extract farmer information"""
        
        prompt = f"""
You are an expert information extraction system specialized in extracting farmer information from text. 
Extract the following information from the given text and return it in JSON format.

Text to analyze: "{text}"

Extract these fields if present:
- name: Farmer's name
- age: Age in years (number only)
- gender: male/female
- phone_number: Phone number
- state: State name
- district: District name
- village: Village name
- land_size_acres: Land size in acres (convert if needed)
- land_ownership: owned/leased/shared
- annual_income: Annual income in rupees (convert lakhs/crores to numbers)
- crops: List of crops grown
- irrigation_type: Type of irrigation used
- family_size: Number of family members
- farming_equipment: Equipment owned
- fertilizers_used: Fertilizers mentioned

Rules:
1. Return ONLY valid JSON format
2. Use null for missing information
3. Convert all measurements to standard units
4. For crops, return as array even if single crop
5. Be precise and don't make assumptions
6. Handle both English and Hindi text

Example output format:
{{
    "name": "Ram Kumar",
    "age": 45,
    "gender": "male",
    "phone_number": "9876543210",
    "state": "Uttar Pradesh",
    "district": "Aligarh",
    "village": "Rampur",
    "land_size_acres": 5.0,
    "land_ownership": "owned",
    "annual_income": 200000,
    "crops": ["wheat", "rice"],
    "irrigation_type": "borewell",
    "family_size": 6,
    "farming_equipment": ["tractor"],
    "fertilizers_used": ["urea", "dap"]
}}

JSON Response:
"""
        
        return prompt
    
    def _parse_ollama_response(self, response: str) -> Dict[str, Any]:
        """Parse Ollama's JSON response into structured entities"""
        entities = {}
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != 0:
                json_str = response[json_start:json_end]
                parsed_data = json.loads(json_str)
                
                # Map parsed data to our entity structure
                entity_mapping = {
                    'name': 'name',
                    'age': 'age',
                    'gender': 'gender',
                    'phone_number': 'phone_number',
                    'state': 'state',
                    'district': 'district',
                    'village': 'village',
                    'land_size_acres': 'land_size_acres',
                    'land_ownership': 'land_ownership',
                    'annual_income': 'annual_income',
                    'crops': 'crops',
                    'irrigation_type': 'irrigation_type',
                    'family_size': 'family_size',
                    'farming_equipment': 'farming_equipment',
                    'fertilizers_used': 'fertilizers_used'
                }
                
                for llm_key, entity_key in entity_mapping.items():
                    if llm_key in parsed_data and parsed_data[llm_key] is not None:
                        entities[entity_key] = parsed_data[llm_key]
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Ollama JSON response: {str(e)}")
            # Fallback: try to extract information using regex
            entities = self._fallback_parse_ollama_response(response)
        except Exception as e:
            logger.warning(f"Error parsing Ollama response: {str(e)}")
        
        return entities
    
    def _fallback_parse_ollama_response(self, response: str) -> Dict[str, Any]:
        """Fallback parser for when JSON parsing fails"""
        entities = {}
        
        # Simple regex patterns to extract key information
        patterns = {
            'name': r'(?:name|नाम)[:=]\s*["\']?([^"\',\n]+)["\']?',
            'age': r'(?:age|उम्र|आयु)[:=]\s*(\d+)',
            'phone_number': r'(?:phone|फोन)[:=]\s*["\']?(\d{10})["\']?',
            'annual_income': r'(?:income|आय)[:=]\s*["\']?(\d+(?:,\d+)*)["\']?'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                entities[key] = match.group(1).strip()
        
        return entities
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess input text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters but keep important punctuation
        text = re.sub(r'[^\w\s.,।?!₹]', ' ', text)
        
        # Normalize common variations
        text = text.replace('रु.', 'रुपये')
        text = text.replace('Rs.', 'rupees')
        text = text.replace('₹', 'rupees')
        
        return text
    
    async def _extract_with_patterns(
        self, text: str, language: str
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Extract entities using pattern matching"""
        entities = {}
        confidence_scores = {}
        
        try:
            # Extract crops
            crops = []
            for crop in self.agricultural_patterns['crops']:
                if crop.lower() in text.lower():
                    crops.append(crop)
            
            if crops:
                entities['crops'] = crops
                confidence_scores['crops'] = 0.8
            
            # Extract land size
            land_size = self._extract_numeric_value(text, 'land_size')
            if land_size:
                entities['land_size_acres'] = float(land_size)
                confidence_scores['land_size_acres'] = 0.9
            
            # Extract income
            income = self._extract_numeric_value(text, 'income')
            if income:
                entities['annual_income'] = self._normalize_income(income, text)
                confidence_scores['annual_income'] = 0.8
            
            # Extract age
            age = self._extract_numeric_value(text, 'age')
            if age:
                entities['age'] = int(age)
                confidence_scores['age'] = 0.9
            
            # Extract family size
            family_size = self._extract_numeric_value(text, 'family_size')
            if family_size:
                entities['family_size'] = int(family_size)
                confidence_scores['family_size'] = 0.8
            
        except Exception as e:
            logger.warning(f"Pattern extraction failed: {str(e)}")
        
        return entities, confidence_scores
    
    def _normalize_income(self, income_str: str, full_text: str) -> int:
        """Normalize income to rupees"""
        try:
            income_num = float(income_str.replace(',', ''))
            
            # Check for lakh/crore indicators
            if any(word in full_text.lower() for word in ['lakh', 'लाख']):
                income_num *= 100000
            elif any(word in full_text.lower() for word in ['crore', 'करोड़']):
                income_num *= 10000000
            
            return int(income_num)
        except:
            return income_str
    
    async def _extract_with_rules(
        self, text: str, doc
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Extract entities using rule-based approach"""
        entities = {}
        confidence_scores = {}

        try:
            # Rule 1: Extract phone numbers
            phone_pattern = r'(?:\+91|91)?[-.\s]?[6-9]\d{9}'
            phone_matches = re.findall(phone_pattern, text)
            if phone_matches:
                entities['phone_number'] = phone_matches[0]
                confidence_scores['phone_number'] = 0.95

            # Rule 2: Extract irrigation type
            irrigation_keywords = {
                'rain fed': ['rain', 'बारिश', 'rainfall'],
                'canal': ['canal', 'नहर'],
                'borewell': ['borewell', 'bore well', 'tube well', 'बोरवेल', 'नलकूप'],
                'drip': ['drip', 'ड्रिप'],
                'sprinkler': ['sprinkler', 'फव्वारा']
            }

            for irrigation_type, keywords in irrigation_keywords.items():
                if any(keyword.lower() in text.lower() for keyword in keywords):
                    entities['irrigation_type'] = irrigation_type
                    confidence_scores['irrigation_type'] = 0.7
                    break

            # Rule 3: Extract known location mentions
            locations = []
            for location in self.location_patterns['states'] + self.location_patterns['districts']:
                if location.lower() in text.lower():
                    locations.append(location)
            
            if locations:
                entities['locations'] = locations
                confidence_scores['locations'] = 0.85

            # Rule 4: Extract gender information
            gender_keywords = {
                'male': ['sir', 'mr', 'साहब', 'भाई', 'जी'],
                'female': ['madam', 'mrs', 'ms', 'मैडम', 'बहन', 'जी']
            }
            
            for gender, keywords in gender_keywords.items():
                if any(keyword.lower() in text.lower() for keyword in keywords):
                    entities['gender'] = gender
                    confidence_scores['gender'] = 0.6
                    break

            # Rule 5: Extract land ownership type
            ownership_keywords = {
                'owned': ['own', 'owned', 'अपना', 'स्वामित्व'],
                'leased': ['lease', 'leased', 'rent', 'किराया', 'लीज'],
                'shared': ['share', 'shared', 'साझा', 'बंटाई']
            }
            
            for ownership_type, keywords in ownership_keywords.items():
                if any(keyword.lower() in text.lower() for keyword in keywords):
                    entities['land_ownership'] = ownership_type
                    confidence_scores['land_ownership'] = 0.7
                    break

        except Exception as e:
            logger.warning(f"Rule-based extraction failed: {str(e)}")

        return entities, confidence_scores

    async def _extract_with_ner(self, doc) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Extract entities using spaCy's NER (only for English)"""
        entities = {}
        confidence_scores = {}

        try:
            for ent in doc.ents:
                if ent.label_ == "GPE":  # Geo-political entity
                    entities.setdefault("locations", []).append(ent.text)
                    confidence_scores["locations"] = 0.7
                elif ent.label_ == "PERSON":
                    entities["name"] = ent.text
                    confidence_scores["name"] = 0.6
                elif ent.label_ == "MONEY":
                    entities["annual_income"] = ent.text
                    confidence_scores["annual_income"] = 0.8
                elif ent.label_ == "QUANTITY":
                    if any(unit in ent.text.lower() for unit in ['acre', 'hectare']):
                        entities["land_size_acres"] = ent.text
                        confidence_scores["land_size_acres"] = 0.7

        except Exception as e:
            logger.warning(f"NER extraction failed: {str(e)}")

        return entities, confidence_scores

    def _extract_numeric_value(self, text: str, category: str) -> Optional[str]:
        """Extract numeric value from text using regex for a given category"""
        patterns = self.numeric_patterns.get(category, [])
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).replace(",", "")
        return None

    def _build_farmer_info(self, entities: Dict[str, Any]) -> FarmerInfo:
        """Build FarmerInfo dataclass object from extracted entities"""
        # Handle locations - separate state and district
        locations = entities.get('locations', [])
        state = None
        district = None
        
        if locations:
            for location in locations:
                if location.lower() in [s.lower() for s in self.location_patterns['states']]:
                    state = location
                elif location.lower() in [d.lower() for d in self.location_patterns['districts']]:
                    district = location
        
        return FarmerInfo(
            name=entities.get("name"),
            phone_number=entities.get("phone_number"),
            age=entities.get("age"),
            gender=entities.get("gender"),
            family_size=entities.get("family_size"),
            state=entities.get("state") or state,
            district=entities.get("district") or district,
            village=entities.get("village"),
            land_size_acres=entities.get("land_size_acres"),
            land_ownership=entities.get("land_ownership"),
            annual_income=entities.get("annual_income"),
            crops=entities.get("crops", []),
            irrigation_type=entities.get("irrigation_type")
        )
    
    async def is_ready(self) -> bool:
        """Check if the agent is ready"""
        return len(self.nlp_models) > 0
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.nlp_models.clear()
            self.matchers.clear()
            self.ollama_client = None
            logger.info("Enhanced NLU agent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during NLU cleanup: {str(e)}")
    
    async def get_supported_entities(self) -> List[str]:
        """Get list of supported entity types"""
        return [
            'name', 'age', 'gender', 'phone_number', 'state', 'district', 'village',
            'land_size_acres', 'land_ownership', 'crops', 'irrigation_type',
            'annual_income', 'family_size', 'farming_equipment', 'fertilizers_used'
        ]
    
    async def set_ollama_model(self, model_name: str):
        """Set the Ollama model to use"""
        if self.ollama_enabled:
            self.ollama_model = model_name
            logger.info(f"Ollama model set to: {model_name}")
    
    async def get_ollama_models(self) -> List[str]:
        """Get list of available Ollama models"""
        if not self.ollama_enabled or not self.ollama_client:
            return []
        
        try:
            models = await asyncio.get_event_loop().run_in_executor(
                None, self.ollama_client.list
            )
            return [model['name'] for model in models['models']]
        except Exception as e:
            logger.error(f"Failed to get Ollama models: {str(e)}")
            return []
    
    def get_extraction_statistics(self) -> Dict[str, Any]:
        """Get statistics about extraction performance"""
        return {
            "supported_languages": list(self.nlp_models.keys()),
            "total_crop_patterns": len(self.agricultural_patterns.get('crops', [])),
            "total_location_patterns": len(self.location_patterns.get('states', []) + self.location_patterns.get('districts', [])),
            "numeric_pattern_categories": list(self.numeric_patterns.keys()),
            "ollama_enabled": self.ollama_enabled,
            "ollama_model": self.ollama_model if self.ollama_enabled else None
        }