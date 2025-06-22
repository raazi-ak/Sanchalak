import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from database import Database
from models import FarmerVerification, VerificationStatus, EKYCStatus
from multilingual_messages import messages

logger = logging.getLogger(__name__)

class UserStateManager:
    """Manages user state, language preferences, and context"""
    
    # Language code mapping from long names to locale file codes
    LANGUAGE_CODE_MAPPING = {
        "english": "en",
        "hindi": "hi", 
        "bengali": "bn",
        "telugu": "te",
        "marathi": "mr",
        "tamil": "ta",
        "gujarati": "gu",
        "punjabi": "pa",
        "kannada": "kn",
        "malayalam": "ml",
        "odia": "or",
        "assamese": "as",
        "urdu": "ur",
        "nepali": "ne",
        "sanskrit": "sa"
    }

    def __init__(self, database: Database):
        self.db = database
        self._user_cache = {}  # Cache user data for performance
    
    def _get_locale_code(self, language_name: str) -> str:
        """Convert long language name to locale file code"""
        return self.LANGUAGE_CODE_MAPPING.get(language_name.lower(), "en")
    
    async def get_or_create_user(self, telegram_user_id: int, first_name: str = None, username: str = None) -> FarmerVerification:
        """Get existing user or create new one with proper state management"""
        try:
            # Check cache first
            if telegram_user_id in self._user_cache:
                cached_user = self._user_cache[telegram_user_id]
                # Refresh cache every 5 minutes
                if (datetime.now() - cached_user['cached_at']).seconds < 300:
                    return cached_user['user']
            
            # Get from database
            farmer = await self.db.get_farmer_by_telegram_id(telegram_user_id)
            
            if farmer:
                # Update last login
                await self.db.update_farmer_login(farmer.farmer_id)
                
                # Cache the user
                self._user_cache[telegram_user_id] = {
                    'user': farmer,
                    'cached_at': datetime.now()
                }
                
                logger.info(f"Retrieved existing user: {farmer.farmer_id} (Language: {farmer.language_preference})")
                return farmer
            else:
                # Create new user with default language (Hindi)
                farmer_data = {
                    "telegram_user_id": telegram_user_id,
                    "name": first_name,
                    "username": username,
                    "phone": None,  # Will be collected later
                    "language_preference": "hindi",  # Default
                    "verification_status": VerificationStatus.PENDING,
                    "ekyc_status": EKYCStatus.NOT_STARTED
                }
                
                farmer = await self.db.create_farmer(farmer_data)
                
                # Cache the new user
                self._user_cache[telegram_user_id] = {
                    'user': farmer,
                    'cached_at': datetime.now()
                }
                
                logger.info(f"Created new user: {farmer.farmer_id} (Default language: Hindi)")
                return farmer
                
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {e}")
            raise
    
    async def update_user_language(self, telegram_user_id: int, language: str) -> bool:
        """Update user's language preference and refresh cache"""
        try:
            farmer = await self.get_or_create_user(telegram_user_id)
            
            # Update in database
            success = await self.db.update_farmer_language(farmer.farmer_id, language)
            
            if success:
                # Force clear cache for this user
                if telegram_user_id in self._user_cache:
                    del self._user_cache[telegram_user_id]
                
                # Refresh user data from database to get updated language
                updated_farmer = await self.db.get_farmer_by_telegram_id(telegram_user_id)
                if updated_farmer:
                    # Update cache with fresh data
                    self._user_cache[telegram_user_id] = {
                        'user': updated_farmer,
                        'cached_at': datetime.now()
                    }
                    
                    logger.info(f"Successfully updated language for user {farmer.farmer_id} to {language}")
                    logger.info(f"Verified language in cache: {updated_farmer.language_preference}")
                    return True
                else:
                    logger.error(f"Failed to retrieve updated farmer data for user {telegram_user_id}")
                    return False
            else:
                logger.error(f"Database update failed for user {farmer.farmer_id} language: {language}")
                return False
            
        except Exception as e:
            logger.error(f"Error updating user language: {e}")
            return False
    
    async def get_user_language(self, telegram_user_id: int) -> str:
        """Get user's preferred language with caching"""
        try:
            farmer = await self.get_or_create_user(telegram_user_id)
            language = farmer.language_preference or "hindi"
            logger.debug(f"Retrieved language for user {telegram_user_id}: {language}")
            return language
        except Exception as e:
            logger.error(f"Error getting user language for {telegram_user_id}: {e}")
            return "hindi"  # Fallback
    
    async def update_user_phone(self, telegram_user_id: int, phone: str) -> bool:
        """Update user's phone number"""
        try:
            farmer = await self.get_or_create_user(telegram_user_id)
            
            # Update phone in database (implement this method in database.py)
            # For now, we'll update via the farmer object
            farmer.phone = phone
            # You would need to implement update_farmer_phone in database.py
            
            # Update cache
            if telegram_user_id in self._user_cache:
                self._user_cache[telegram_user_id]['user'].phone = phone
                self._user_cache[telegram_user_id]['cached_at'] = datetime.now()
            
            logger.info(f"Updated phone for user {farmer.farmer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user phone: {e}")
            return False
    
    async def get_localized_message(self, telegram_user_id: int, message_key: str, lang_code: str = None, **kwargs) -> str:
        """Get message in user's preferred language or specified language"""
        try:
            if lang_code:
                # Use specified language code
                user_language = lang_code
            elif telegram_user_id:
                # Get user's saved language preference
                user_language = await self.get_user_language(telegram_user_id)
            else:
                # Default language for new users
                user_language = "hindi"
                
            # Convert long language name to locale code
            locale_code = self._get_locale_code(user_language)
            
            return messages.get_message(message_key, locale_code, **kwargs)
        except Exception as e:
            logger.error(f"Error getting localized message: {e}")
            return messages.get_message(message_key, "hi", **kwargs)  # Fallback to Hindi locale code
    
    async def get_user_context(self, telegram_user_id: int) -> Dict[str, Any]:
        """Get complete user context for personalized responses"""
        try:
            farmer = await self.get_or_create_user(telegram_user_id)
            
            return {
                "farmer_id": farmer.farmer_id,
                "name": farmer.name,
                "phone": farmer.phone,
                "language": farmer.language_preference,
                "verification_status": farmer.verification_status,
                "ekyc_status": farmer.ekyc_status,
                "is_verified": farmer.verification_status == VerificationStatus.VERIFIED,
                "registration_complete": farmer.phone is not None,
                "created_at": farmer.created_at,
                "last_login": farmer.last_login
            }
            
        except Exception as e:
            logger.error(f"Error getting user context: {e}")
            return {
                "farmer_id": None,
                "name": None,
                "phone": None,
                "language": "hindi",
                "verification_status": VerificationStatus.PENDING,
                "ekyc_status": EKYCStatus.NOT_STARTED,
                "is_verified": False,
                "registration_complete": False,
                "created_at": None,
                "last_login": None
            }
    
    async def is_user_registered(self, telegram_user_id: int) -> bool:
        """Check if user has completed registration"""
        try:
            context = await self.get_user_context(telegram_user_id)
            return context["registration_complete"]
        except Exception as e:
            logger.error(f"Error checking user registration: {e}")
            return False
    
    async def clear_user_cache(self, telegram_user_id: int = None):
        """Clear user cache (for testing or forced refresh)"""
        if telegram_user_id:
            if telegram_user_id in self._user_cache:
                del self._user_cache[telegram_user_id]
                logger.info(f"Cleared cache for user {telegram_user_id}")
        else:
            self._user_cache.clear()
            logger.info("Cleared all user cache")
    
    async def get_user_stats(self, telegram_user_id: int) -> Dict[str, Any]:
        """Get user statistics and activity"""
        try:
            farmer = await self.get_or_create_user(telegram_user_id)
            stats = await self.db.get_farmer_stats(farmer.farmer_id)
            
            return {
                "total_sessions": stats.get("total_sessions", 0),
                "completed_sessions": stats.get("completed_sessions", 0),
                "active_sessions": stats.get("active_sessions", 0),
                "member_since": farmer.created_at,
                "last_activity": farmer.last_login,
                "language": farmer.language_preference,
                "verification_status": farmer.verification_status
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                "total_sessions": 0,
                "completed_sessions": 0,
                "active_sessions": 0,
                "member_since": None,
                "last_activity": None,
                "language": "hindi",
                "verification_status": VerificationStatus.PENDING
            } 