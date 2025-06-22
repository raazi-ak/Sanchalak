import httpx
import json
import logging
from django.conf import settings
from django.utils import timezone
from .models import FarmerUser, ChatSession, SessionMessage, SchemeEligibility
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for database operations"""
    
    @staticmethod
    async def get_or_create_farmer(telegram_user_id: int, name: str = None) -> FarmerUser:
        """Get existing farmer or create new one"""
        try:
            farmer = await FarmerUser.objects.aget(telegram_user_id=telegram_user_id)
            # Update last login
            farmer.last_login = timezone.now()
            await farmer.asave()
            return farmer
        except FarmerUser.DoesNotExist:
            # Create new farmer
            farmer = FarmerUser(
                farmer_id=str(uuid.uuid4()),
                telegram_user_id=telegram_user_id,
                name=name
            )
            await farmer.asave()
            logger.info(f"Created new farmer: {farmer.farmer_id}")
            return farmer
    
    @staticmethod
    async def update_farmer_language(farmer_id: str, language: str) -> bool:
        """Update farmer's language preference"""
        try:
            farmer = await FarmerUser.objects.aget(farmer_id=farmer_id)
            farmer.language_preference = language
            await farmer.asave()
            return True
        except FarmerUser.DoesNotExist:
            return False
    
    @staticmethod
    async def create_session(farmer_id: str, telegram_user_id: int) -> ChatSession:
        """Create new chat session"""
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            farmer_id=farmer_id,
            telegram_user_id=telegram_user_id
        )
        await session.asave(using='sessions')
        logger.info(f"Created session: {session.session_id}")
        return session
    
    @staticmethod
    async def get_active_session(telegram_user_id: int) -> Optional[ChatSession]:
        """Get active session for user"""
        try:
            return await ChatSession.objects.using('sessions').aget(
                telegram_user_id=telegram_user_id,
                status='active'
            )
        except ChatSession.DoesNotExist:
            return None
    
    @staticmethod
    async def add_message(session_id: str, message_type: str, content: str, file_path: str = None) -> SessionMessage:
        """Add message to session"""
        message = SessionMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            message_type=message_type,
            content=content,
            file_path=file_path
        )
        await message.asave(using='sessions')
        
        # Update session message count
        session = await ChatSession.objects.using('sessions').aget(session_id=session_id)
        session.total_messages += 1
        await session.asave(using='sessions')
        
        return message
    
    @staticmethod
    async def end_session(session_id: str, processing_result: Dict = None) -> bool:
        """End chat session"""
        try:
            session = await ChatSession.objects.using('sessions').aget(session_id=session_id)
            session.status = 'completed'
            session.end_time = timezone.now()
            if processing_result:
                session.processing_result = processing_result
            await session.asave(using='sessions')
            return True
        except ChatSession.DoesNotExist:
            return False


class OrchestratorService:
    """Service for communicating with orchestrator"""
    
    @staticmethod
    async def process_session(session_id: str, messages: list) -> Dict[str, Any]:
        """Send session to orchestrator for processing"""
        try:
            # Prepare payload
            payload = {
                "session_id": session_id,
                "messages": messages,
                "timestamp": timezone.now().isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ORCHESTRATOR_URL}/api/process_session",
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"Orchestrator processed session {session_id}")
                return result
                
        except httpx.RequestError as e:
            logger.error(f"Failed to communicate with orchestrator: {e}")
            return {"error": "orchestrator_unavailable", "message": str(e)}
        except Exception as e:
            logger.error(f"Error processing session: {e}")
            return {"error": "processing_failed", "message": str(e)}
    
    @staticmethod
    async def check_eligibility(farmer_data: Dict, scheme_code: str) -> Dict[str, Any]:
        """Check scheme eligibility via orchestrator"""
        try:
            payload = {
                "farmer_data": farmer_data,
                "scheme_code": scheme_code
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ORCHESTRATOR_URL}/api/check_eligibility",
                    json=payload,
                    timeout=15.0
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Eligibility check failed: {e}")
            return {"eligible": False, "error": str(e)}
    
    @staticmethod
    async def generate_form(farmer_id: str, scheme_code: str) -> Dict[str, Any]:
        """Generate form via orchestrator"""
        try:
            payload = {
                "farmer_id": farmer_id,
                "scheme_code": scheme_code
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ORCHESTRATOR_URL}/api/generate_form",
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Form generation failed: {e}")
            return {"success": False, "error": str(e)} 