import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """OpenRouter API client for LLM responses"""
    
    def __init__(self):
        self.base_url = settings.openrouter_base_url
        self.api_key = settings.openrouter_api_key
        self.default_model = settings.quick_response_model
        
        # Enhanced farming-focused system prompt with comprehensive bot information
        self.system_prompt = """You are Sanchalak, India's #1 AI assistant built EXCLUSIVELY for Indian farmers.

ABOUT SANCHALAK:
Sanchalak is a comprehensive AI-powered farming assistant designed to help Indian farmers with government schemes, agricultural advice, and farming solutions. The bot supports 15+ Indian languages and provides both voice and text assistance.

WHAT SANCHALAK DOES:
• Government scheme information and eligibility (PM-KISAN, PMFBY, KCC, PMAY, etc.)
• Personalized agricultural advice and farming solutions
• Crop cultivation guidance (planting, varieties, harvesting)
• Disease and pest identification and treatment
• Weather-based farming recommendations
• Soil management and fertilizer advice
• Irrigation and water management solutions
• Market prices and crop selling strategies
• Organic and sustainable farming practices
• Livestock, poultry, and dairy farming guidance
• Agricultural equipment and machinery information
• Financial schemes and credit assistance for farmers

AVAILABLE COMMANDS (explain when asked):
• /start - Register and start using Sanchalak
• /help - Get comprehensive information about Sanchalak
• /start_log - Begin all-day personalized advice session
• /end_log - End session and receive detailed analysis
• /status - Check registration and session status
• /language - Change language preference

KEY FEATURES:
- All-day sessions: Farmers can log activities throughout the day
- Voice support in multiple Indian languages
- Personalized scheme recommendations based on farmer profile
- Real-time agricultural guidance
- Secure data handling with farmer privacy protection

STRICT USAGE RULES - NEVER VIOLATE:
1. ONLY discuss farming, agriculture, government schemes, and farmer welfare topics
2. NEVER answer questions about politics, technology, entertainment, general knowledge, health, etc.
3. If asked non-farming questions, politely redirect: "I can only help with farming and agricultural matters. Please ask farming-related questions."
4. Always keep responses practical, actionable, and farmer-friendly
5. For complex situations requiring detailed analysis, suggest using "/start_log" command
6. When explaining Sanchalak's purpose, mention it's specifically built for Indian farmers

RESPONSE STYLE:
- Use simple, farmer-friendly language
- Provide actionable advice
- Include relevant government scheme information when applicable
- Be encouraging and supportive
- Keep responses concise but comprehensive"""

    async def generate_response(
        self, 
        user_message: str, 
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None
    ) -> str:
        """Generate response using OpenRouter API"""
        
        try:
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://sanchalak.ai",  # Optional: for app identification
                "X-Title": "Sanchalak - Farmer Assistant"
            }
            
            # Prepare messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]
            
            # Add context if provided
            if context:
                # Add user language preference to system prompt
                user_language = context.get("user_language", "hindi")
                language_names = {
                    "hindi": "Hindi", "english": "English", "bengali": "Bengali", 
                    "telugu": "Telugu", "marathi": "Marathi", "tamil": "Tamil",
                    "gujarati": "Gujarati", "punjabi": "Punjabi", "kannada": "Kannada", 
                    "malayalam": "Malayalam", "odia": "Odia", "assamese": "Assamese",
                    "urdu": "Urdu", "rajasthani": "Rajasthani", "bhojpuri": "Bhojpuri"
                }
                language_name = language_names.get(user_language.lower(), "Hindi")
                
                # Enhanced strict language and script instruction
                language_configs = {
                    "hindi": {"script": "Devanagari (हिंदी)", "example": "नमस्ते, फसल"},
                    "english": {"script": "Latin (English)", "example": "Hello, crop"},
                    "bengali": {"script": "Bengali (বাংলা)", "example": "নমস্কার, ফসল"},
                    "telugu": {"script": "Telugu (తెలుగు)", "example": "నమస్కారం, పంట"},
                    "marathi": {"script": "Devanagari (मराठी)", "example": "नमस्कार, पिक"},
                    "tamil": {"script": "Tamil (தமிழ்)", "example": "வணக்கம், பயிர்"},
                    "gujarati": {"script": "Gujarati (ગુજરાતી)", "example": "નમસ્તે, પાક"},
                    "punjabi": {"script": "Gurmukhi (ਪੰਜਾਬੀ)", "example": "ਸਤਸ੍ਰੀ ਅਕਾਲ, ਫਸਲ"},
                    "kannada": {"script": "Kannada (ಕನ್ನಡ)", "example": "ನಮಸ್ಕಾರ, ಬೆಳೆ"},
                    "malayalam": {"script": "Malayalam (മലയാളം)", "example": "നമസ്കാരം, വിള"},
                    "odia": {"script": "Odia (ଓଡିଆ)", "example": "ନମସ୍କାର, ଫସଲ"},
                    "assamese": {"script": "Assamese (অসমীয়া)", "example": "নমস্কাৰ, শস্য"}
                }
                
                lang_config = language_configs.get(user_language.lower(), language_configs["hindi"])
                
                # Strict enforcement instruction
                language_instruction = f"""CRITICAL REQUIREMENTS - FOLLOW EXACTLY:

1. LANGUAGE & SCRIPT: You MUST respond ONLY in {language_name} using {lang_config['script']} script
   - NEVER use Latin/Roman script for non-English languages
   - Example: Write "{lang_config['example'].split(', ')[1]}" NOT "fasal" or "crop"

2. FARMING FOCUS ONLY: You can ONLY discuss these topics:
   - Government schemes for farmers (PM-KISAN, PMFBY, KCC, etc.)
   - Crops, seeds, planting, harvesting
   - Soil, fertilizers, pesticides, irrigation
   - Weather, seasons, farming calendar
   - Livestock, poultry, dairy farming
   - Agricultural equipment, machinery
   - Market prices, selling crops
   - Organic farming, sustainable practices

3. FORBIDDEN TOPICS: If asked about anything else (politics, technology, general knowledge, entertainment, health, etc.), politely say:
   "मुझे केवल कृषि और किसान योजनाओं के बारे में ही बात करने की अनुमति है। कृपया खेती से संबंधित प्रश्न पूछें।" (adapt to user's language)

4. RESPONSE STYLE: Keep responses concise, practical, and farmer-friendly."""

                messages.append({"role": "system", "content": language_instruction})
                
                # Add farmer context if available
                farmer_info = context.get("farmer_info", {})
                if farmer_info:
                    context_msg = f"User context: Farmer from {farmer_info.get('location', 'India')}, "
                    context_msg += f"grows {', '.join(farmer_info.get('crops', []))}."
                    messages.append({"role": "system", "content": context_msg})
            
            messages.append({"role": "user", "content": user_message})
            
            # Prepare request payload
            payload = {
                "model": model or self.default_model,
                "messages": messages,
                "max_tokens": 512,
                "temperature": 0.7,
                "stream": False
            }
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        message_content = data["choices"][0]["message"]["content"]
                        logger.info(f"Generated LLM response successfully")
                        return message_content.strip()
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error_text}")
                        return self._get_fallback_response(user_message)
                        
        except asyncio.TimeoutError:
            logger.error("OpenRouter API timeout")
            return "Sorry, I'm experiencing some delays. Please try again in a moment."
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return self._get_fallback_response(user_message)
    
    def _get_fallback_response(self, user_message: str) -> str:
        """Provide fallback response when LLM fails"""
        
        # Simple keyword-based responses
        message_lower = user_message.lower()
        
        # Check if user is asking about what the bot is for or its purpose
        if any(word in message_lower for word in ["what is sanchalak", "sanchalak kya hai", "संचालक क्या है", "bot kya hai", "what do you do", "help me", "commands", "कमांड"]):
            return """🌾 **Sanchalak - भारत का #1 किसान AI असिस्टेंट**

मैं भारतीय किसानों के लिए विशेष रूप से बनाया गया AI सहायक हूं।

**मैं इसमें आपकी मदद कर सकता हूं:**
• सरकारी योजनाएं (PM-KISAN, PMFBY, KCC)
• फसल की बीमारी और उपचार
• खेती की तकनीक और सलाह
• बाजार की कीमतें और मौसम सलाह
• पशुपालन और डेयरी फार्मिंग
• कृषि उपकरण की जानकारी

**मुख्य कमांड्स:**
• /help - पूरी जानकारी देखें
• /start_log - व्यक्तिगत सलाह सेशन शुरू करें
• /status - अपनी स्थिति देखें

विस्तृत जानकारी के लिए /help टाइप करें!"""
        
        elif any(word in message_lower for word in ["pm-kisan", "pm kisan", "किसान सम्मान"]):
            return """🌾 **PM-KISAN Scheme**

✅ **Eligibility**: Farmers with up to 5 acres of land
💰 **Benefit**: ₹6,000 per year in 3 installments
📝 **Apply**: Online at pmkisan.gov.in

For detailed eligibility check, use /start_log command!"""

        elif any(word in message_lower for word in ["pmfby", "crop insurance", "फसल बीमा"]):
            return """🛡️ **PM Fasal Bima Yojana (PMFBY)**

✅ **Coverage**: Crop loss due to natural disasters
💰 **Premium**: Very low farmer contribution
📝 **Apply**: Through banks/insurance companies

For personalized advice, use /start_log command!"""

        elif any(word in message_lower for word in ["kcc", "credit card", "किसान क्रेडिट"]):
            return """💳 **Kisan Credit Card (KCC)**

✅ **Purpose**: Agricultural credit at low interest
💰 **Limit**: Based on land holding & crop pattern
📝 **Apply**: Through banks and cooperatives

For eligibility check, use /start_log command!"""

        elif any(word in message_lower for word in ["weather", "मौसम", "बारिश"]):
            return """🌤️ **Weather Guidance**

For accurate weather forecasts and crop-specific advice based on your location, please use the /start_log command to share your location and farming details.

I can provide personalized weather-based recommendations!"""

        elif any(word in message_lower for word in ["hello", "hi", "नमस्ते", "नमस्कार"]):
            return """🌾 **नमस्कार! Sanchalak में आपका स्वागत है**

मैं केवल कृषि और किसान योजनाओं में आपकी मदद कर सकता हूं:

🔸 सरकारी योजनाएं (PM-KISAN, PMFBY, KCC)
🔸 फसल की जानकारी और सलाह
🔸 मिट्टी, खाद, सिंचाई की जानकारी
🔸 मौसम आधारित सलाह

**विस्तृत सहायता के लिए**: /start_log का उपयोग करें
**सभी कमांड्स देखने के लिए**: /help टाइप करें

कृपया खेती से संबंधित प्रश्न पूछें!"""
        
        else:
            return """🌾 **Sanchalak - केवल कृषि सहायता**

⚠️ मैं केवल इन विषयों पर बात कर सकता हूं:
🔸 किसान योजनाएं (PM-KISAN, PMFBY, KCC)
🔸 फसल उत्पादन और बीज
🔸 खाद, दवाई, सिंचाई
🔸 पशुपालन और डेयरी
🔸 कृषि उपकरण
🔸 मौसम और बुआई

**व्यक्तिगत सलाह के लिए**: /start_log का उपयोग करें
**सभी कमांड्स देखने के लिए**: /help टाइप करें

कृपया कृषि से संबंधित प्रश्न पूछें!"""

    async def generate_scheme_summary(self, schemes: List[str]) -> str:
        """Generate summary of multiple schemes"""
        
        if not schemes:
            return "No specific schemes to summarize."
        
        scheme_query = f"Provide a brief summary of these Indian government schemes for farmers: {', '.join(schemes)}"
        
        return await self.generate_response(
            scheme_query,
            model=settings.detailed_model  # Use better model for summaries
        )

    async def answer_faq(self, question: str) -> str:
        """Answer common farming FAQs"""
        
        faq_prompt = f"""Answer this common farming question concisely: {question}

If this requires detailed analysis of the farmer's specific situation, suggest using /start_log for comprehensive help."""
        
        return await self.generate_response(faq_prompt)

    async def translate_message(self, text: str, target_language: str = "hi") -> str:
        """Translate text to target language"""
        
        if target_language == "en":
            return text  # Already in English
        
        language_names = {
            "hindi": "Hindi",
            "english": "English", 
            "bengali": "Bengali",
            "telugu": "Telugu",
            "marathi": "Marathi",
            "tamil": "Tamil",
            "gujarati": "Gujarati", 
            "punjabi": "Punjabi",
            "kannada": "Kannada",
            "malayalam": "Malayalam",
            "odia": "Odia",
            "assamese": "Assamese",
            "urdu": "Urdu",
            "rajasthani": "Rajasthani",
            "bhojpuri": "Bhojpuri"
        }
        
        target_lang_name = language_names.get(target_language.lower(), "Hindi")
        
        translate_prompt = f"Translate this text to {target_lang_name}, keeping agricultural and technical terms appropriate for farmers: {text}"
        
        return await self.generate_response(translate_prompt)

    def is_complex_query(self, message: str) -> bool:
        """Determine if query needs full AI processing"""
        
        complex_indicators = [
            "my farm", "my crop", "my land", "मेरा खेत", "मेरी फसल",
            "should i", "what should", "क्या करना चाहिए", "सलाह दें",
            "eligible", "पात्र", "qualify", "योग्य",
            "acres", "एकड़", "hectare", "हेक्टेयर",
            "income", "आय", "earn", "कमाना"
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in complex_indicators)

# Global LLM client instance
llm_client = OpenRouterClient() 