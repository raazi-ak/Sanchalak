import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from config import settings
from models import (
    FarmerVerification, SessionLog, LogMessage, 
    VerificationStatus, SessionStatus, MessageType, EKYCStatus
)

logger = logging.getLogger(__name__)

class Database:
    """Async MongoDB database manager"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.farmer_verification: Optional[AsyncIOMotorCollection] = None
        self.session_logs: Optional[AsyncIOMotorCollection] = None
    
    async def connect(self):
        """Connect to MongoDB with separate databases"""
        try:
            self.client = AsyncIOMotorClient(settings.mongo_uri)
            
            # Separate databases for users and sessions
            self.user_db = self.client["sanchalak_users"]
            self.session_db = self.client["sanchalak_sessions"]
            
            # Collections
            self.farmer_verification = self.user_db["farmer_verification"]
            self.session_logs = self.session_db["session_logs"]
            
            # Create indexes for better performance
            await self._create_indexes()
            
            logger.info("Connected to MongoDB successfully with separate databases")
            logger.info("User data: sanchalak_users, Session data: sanchalak_sessions")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def _create_indexes(self):
        """Create database indexes"""
        try:
            # Farmer verification indexes
            await self.farmer_verification.create_index("farmer_id", unique=True)
            await self.farmer_verification.create_index("phone", unique=True)
            await self.farmer_verification.create_index("telegram_user_id", unique=True)
            
            # Session logs indexes
            await self.session_logs.create_index("session_id", unique=True)
            await self.session_logs.create_index("farmer_id")
            await self.session_logs.create_index("telegram_user_id")
            await self.session_logs.create_index("start_time")
            await self.session_logs.create_index("status")
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Failed to create indexes: {e}")
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    # Farmer Verification Operations
    async def create_farmer(self, farmer_data: Dict[str, Any]) -> FarmerVerification:
        """Create a new farmer verification record"""
        try:
            farmer = FarmerVerification(**farmer_data)
            await self.farmer_verification.insert_one(farmer.dict())
            logger.info(f"Created farmer: {farmer.farmer_id}")
            return farmer
            
        except DuplicateKeyError:
            raise ValueError("Farmer with this phone/telegram_user_id already exists")
        except Exception as e:
            logger.error(f"Failed to create farmer: {e}")
            raise
    
    async def get_farmer_by_telegram_id(self, telegram_user_id: int) -> Optional[FarmerVerification]:
        """Get farmer by Telegram user ID"""
        try:
            doc = await self.farmer_verification.find_one({"telegram_user_id": telegram_user_id})
            if doc:
                return FarmerVerification(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get farmer by telegram ID: {e}")
            return None
    
    async def get_farmer_by_phone(self, phone: str) -> Optional[FarmerVerification]:
        """Get farmer by phone number"""
        try:
            doc = await self.farmer_verification.find_one({"phone": phone})
            if doc:
                return FarmerVerification(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get farmer by phone: {e}")
            return None
    
    async def update_farmer_login(self, farmer_id: str) -> bool:
        """Update farmer's last login time"""
        try:
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": {"last_login": datetime.now()}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update farmer login: {e}")
            return False
    
    async def update_farmer_language(self, farmer_id: str, language: str) -> bool:
        """Update farmer's language preference"""
        try:
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": {"language_preference": language}}
            )
            logger.info(f"Updated language for farmer {farmer_id} to {language}")
            # Return True if the farmer exists (matched_count > 0), even if no modification was needed
            return result.matched_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update farmer language: {e}")
            return False
    
    async def update_farmer(self, farmer_id: str, update_data: Dict[str, Any]) -> bool:
        """Update farmer information"""
        try:
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": update_data}
            )
            logger.info(f"Updated farmer {farmer_id} with data: {update_data}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update farmer: {e}")
            return False
    
    async def verify_farmer(self, farmer_id: str) -> bool:
        """Mark farmer as verified"""
        try:
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": {"verification_status": VerificationStatus.VERIFIED}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to verify farmer: {e}")
            return False
    
    # eKYC Operations
    async def update_aadhaar_verification(self, farmer_id: str, aadhaar_number: str) -> bool:
        """Update farmer's Aadhaar verification"""
        try:
            # Hash the Aadhaar number for security (in production, use proper encryption)
            import hashlib
            hashed_aadhaar = hashlib.sha256(aadhaar_number.encode()).hexdigest()
            last_digits = aadhaar_number.replace(" ", "")[-4:]
            
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": {
                    "ekyc_status": "aadhaar_verified",
                    "aadhaar_number": hashed_aadhaar,
                    "aadhaar_last_digits": last_digits,
                    "ekyc_completed_at": datetime.now(),
                    "verification_status": VerificationStatus.VERIFIED
                }}
            )
            logger.info(f"Updated Aadhaar verification for farmer {farmer_id}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update Aadhaar verification: {e}")
            return False
    
    async def update_photo_verification(self, farmer_id: str, verification_success: bool) -> bool:
        """Update farmer's photo verification status"""
        try:
            status = "photo_verified" if verification_success else "not_started"
            update_data = {
                "photo_verification_status": verification_success,
                "ekyc_status": status
            }
            
            if verification_success:
                update_data["ekyc_completed_at"] = datetime.now()
                update_data["verification_status"] = VerificationStatus.VERIFIED
            
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": update_data}
            )
            logger.info(f"Updated photo verification for farmer {farmer_id}: {verification_success}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to update photo verification: {e}")
            return False
    
    async def skip_ekyc_verification(self, farmer_id: str) -> bool:
        """Mark eKYC as skipped for farmer"""
        try:
            result = await self.farmer_verification.update_one(
                {"farmer_id": farmer_id},
                {"$set": {
                    "ekyc_status": "skipped",
                    "verification_status": VerificationStatus.VERIFIED  # Still allow basic access
                }}
            )
            logger.info(f"Skipped eKYC verification for farmer {farmer_id}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to skip eKYC verification: {e}")
            return False
    
    # Session Operations
    async def create_session(self, farmer_id: str, telegram_user_id: int) -> SessionLog:
        """Create a new session log"""
        try:
            session = SessionLog(
                farmer_id=farmer_id,
                telegram_user_id=telegram_user_id
            )
            await self.session_logs.insert_one(session.dict())
            logger.info(f"Created session: {session.session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def get_active_session(self, telegram_user_id: int) -> Optional[SessionLog]:
        """Get active session for user"""
        try:
            doc = await self.session_logs.find_one({
                "telegram_user_id": telegram_user_id,
                "status": SessionStatus.ACTIVE
            })
            if doc:
                return SessionLog(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active session: {e}")
            return None
    
    async def add_message_to_session(self, session_id: str, message: LogMessage) -> bool:
        """Add a message to session"""
        try:
            result = await self.session_logs.update_one(
                {"session_id": session_id},
                {"$push": {"messages": message.dict()}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to add message to session: {e}")
            return False
    
    async def end_session(self, session_id: str, processing_result: Optional[Dict] = None) -> bool:
        """End a session and optionally store results"""
        try:
            update_data = {
                "status": SessionStatus.COMPLETED,
                "end_time": datetime.now()
            }
            if processing_result:
                update_data["processing_result"] = processing_result
                
            result = await self.session_logs.update_one(
                {"session_id": session_id},
                {"$set": update_data}
            )
            logger.info(f"Ended session: {session_id}")
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            return False
    
    async def mark_session_processing(self, session_id: str) -> bool:
        """Mark session as processing"""
        try:
            result = await self.session_logs.update_one(
                {"session_id": session_id},
                {"$set": {"status": SessionStatus.PROCESSING}}
            )
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to mark session as processing: {e}")
            return False
    
    async def get_session_by_id(self, session_id: str) -> Optional[SessionLog]:
        """Get session by ID"""
        try:
            doc = await self.session_logs.find_one({"session_id": session_id})
            if doc:
                return SessionLog(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session by ID: {e}")
            return None
    
    async def cleanup_old_sessions(self, hours: int = 24) -> int:
        """Clean up old inactive sessions"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # Mark old active sessions as timeout
            result = await self.session_logs.update_many(
                {
                    "status": SessionStatus.ACTIVE,
                    "start_time": {"$lt": cutoff_time}
                },
                {"$set": {"status": SessionStatus.TIMEOUT}}
            )
            
            logger.info(f"Cleaned up {result.modified_count} old sessions")
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0
    
    async def get_farmer_stats(self, farmer_id: str) -> Dict[str, Any]:
        """Get farmer usage statistics"""
        try:
            pipeline = [
                {"$match": {"farmer_id": farmer_id}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }}
            ]
            
            result = await self.session_logs.aggregate(pipeline).to_list(length=None)
            stats = {item["_id"]: item["count"] for item in result}
            
            return {
                "total_sessions": sum(stats.values()),
                "completed_sessions": stats.get(SessionStatus.COMPLETED, 0),
                "active_sessions": stats.get(SessionStatus.ACTIVE, 0),
                "failed_sessions": stats.get(SessionStatus.FAILED, 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get farmer stats: {e}")
            return {}

# Global database instance
db = Database() 