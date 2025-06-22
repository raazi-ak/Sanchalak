import asyncio
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import aiofiles

from config import settings
from service_health import health_monitor, ServiceStatus

# Import database
from database import Database

from models import SessionLog, LogMessage, MessageType, SessionStatus
from llm_client import llm_client

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions and message buffering"""
    
    def __init__(self, database: Database):
        self.db = database
        self.active_sessions: Dict[int, str] = {}  # telegram_user_id -> session_id
        self.eod_scheduled = False  # Track if EOD cleanup is scheduled
        
    async def start_session(self, telegram_user_id: int, farmer_id: str) -> SessionLog:
        """Start a new logging session for user"""
        
        try:
            # Check if user already has active session
            existing_session = await self.get_active_session(telegram_user_id)
            if existing_session:
                logger.info(f"User {telegram_user_id} already has active session {existing_session.session_id} with {len(existing_session.messages)} messages")
                # End the existing session first
                await self.end_session(telegram_user_id, auto_end=True)
                logger.info(f"Auto-ended existing session {existing_session.session_id} to start new one")
            
            # Create new session
            session = await self.db.create_session(farmer_id, telegram_user_id)
            self.active_sessions[telegram_user_id] = session.session_id
            
            # Schedule EOD cleanup if not already scheduled
            if not self.eod_scheduled:
                await self.schedule_eod_cleanup()
                self.eod_scheduled = True
            
            logger.info(f"Started new session {session.session_id} for user {telegram_user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to start session for user {telegram_user_id}: {e}")
            raise
    
    async def get_active_session(self, telegram_user_id: int) -> Optional[SessionLog]:
        """Get active session for user"""
        
        try:
            # Check memory first
            if telegram_user_id in self.active_sessions:
                session_id = self.active_sessions[telegram_user_id]
                session = await self.db.get_session_by_id(session_id)
                
                if session and session.status == SessionStatus.ACTIVE:
                    return session
                else:
                    # Clean up invalid session from memory
                    del self.active_sessions[telegram_user_id]
            
            # Check database
            session = await self.db.get_active_session(telegram_user_id)
            if session:
                self.active_sessions[telegram_user_id] = session.session_id
                return session
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active session: {e}")
            return None
    
    async def add_text_message(
        self, 
        telegram_user_id: int, 
        content: str
    ) -> bool:
        """Add text message to active session"""
        
        try:
            session = await self.get_active_session(telegram_user_id)
            if not session:
                return False
            
            # Check message limit
            if len(session.messages) >= settings.max_messages_per_session:
                await self.end_session(telegram_user_id, auto_end=True)
                return False
            
            message = LogMessage(
                type=MessageType.TEXT,
                content=content
            )
            
            success = await self.db.add_message_to_session(session.session_id, message)
            if success:
                logger.info(f"Added text message to session {session.session_id}")
                
                # Note: Removed auto-processing on completion indicators
                # Sessions now stay active all day until manually ended or EOD
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add text message: {e}")
            return False
    
    async def add_voice_message(
        self, 
        telegram_user_id: int, 
        file_data: bytes,
        file_extension: str = "ogg"
    ) -> bool:
        """Add voice message to active session"""
        
        try:
            session = await self.get_active_session(telegram_user_id)
            if not session:
                return False
            
            # Check message limit
            if len(session.messages) >= settings.max_messages_per_session:
                await self.end_session(telegram_user_id, auto_end=True)
                return False
            
            # Generate unique filename
            message_count = len(session.messages) + 1
            filename = f"{session.session_id}_audio_{message_count}.{file_extension}"
            file_path = os.path.join(settings.upload_dir, filename)
            
            # Save file to shared volume
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            message = LogMessage(
                type=MessageType.VOICE,
                file_path=filename  # Store relative path
            )
            
            success = await self.db.add_message_to_session(session.session_id, message)
            if success:
                logger.info(f"Added voice message to session {session.session_id}: {filename}")
            else:
                # Clean up file if database operation failed
                try:
                    os.remove(file_path)
                except:
                    pass
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to add voice message: {e}")
            return False
    
    async def end_session(
        self, 
        telegram_user_id: int, 
        auto_end: bool = False
    ) -> Dict[str, Any]:
        """End session and send for processing"""
        
        try:
            # Get active session
            session = await self.get_active_session(telegram_user_id)
            if not session:
                return {"error": "No active session found"}
            
            # Remove from active sessions immediately
            if telegram_user_id in self.active_sessions:
                del self.active_sessions[telegram_user_id]
            
            # Don't process empty sessions or auto-ended sessions
            if not session.messages or auto_end:
                await self.db.end_session(session.session_id, {"status": "ended_early", "reason": "no_messages" if not session.messages else "auto_end"})
                await self._cleanup_session_files(session)
                return {
                    "status": "ended_early",
                    "session_id": session.session_id,
                    "message_count": len(session.messages)
                }
            
            # Check service health before processing
            logger.info(f"🔍 Checking service health before processing session {session.session_id}")
            health_status = await health_monitor.get_cached_health()
            is_available, status_message = health_monitor.get_system_status_message(health_status)
            
            # Prepare session data for orchestrator
            session_data = await self._prepare_session_for_processing(session)
            
            if not is_available:
                # System is down - store session for later processing
                logger.warning(f"🔧 System unavailable for session {session.session_id}, storing for later processing")
                await self.db.end_session(session.session_id, {
                    "status": "queued_for_processing",
                    "reason": "system_unavailable",
                    "health_check_time": datetime.now().isoformat(),
                    "message_count": len(session.messages),
                    "user_message": status_message
                })
                # Don't cleanup files - keep for later processing
                return {
                    "status": "queued_for_processing",
                    "session_id": session.session_id,
                    "message_count": len(session.messages),
                    "user_message": status_message
                }
            
            # Send to orchestrator for processing
            if settings.mock_responses:
                # Use mock response for development
                mock_result = await self._generate_mock_response(session)
                await self.db.end_session(session.session_id, mock_result)
                await self._cleanup_session_files(session)
                return {
                    "status": "completed",
                    "session_id": session.session_id,
                    "result": mock_result
                }
            else:
                # Send to orchestrator for real processing (which will call AI Agent)
                orchestrator_result = await self._send_to_orchestrator(session_data)
                
                if orchestrator_result.get("status") == "completed":
                    await self.db.end_session(session.session_id, orchestrator_result)
                    await self._cleanup_session_files(session)
                    return {
                        "status": "completed",
                        "session_id": session.session_id,
                        "result": orchestrator_result
                    }
                elif orchestrator_result.get("status") == "service_unavailable":
                    # AI analysis service is down - provide specific error handling
                    error_code = orchestrator_result.get("error_code", "AI_AGENT_UNKNOWN")
                    service_status = orchestrator_result.get("service_status", {})
                    detailed_error = orchestrator_result.get("error", "AI Analysis Service unavailable")
                    
                    # Log detailed error for debugging
                    logger.error(f"AI Agent Service Unavailable for session {session.session_id}: {error_code} - {detailed_error}")
                    logger.error(f"Service Status: {service_status}")
                    
                    # Save session with error info for potential retry later
                    error_result = {
                        "status": "service_unavailable",
                        "error_code": error_code,
                        "service_status": service_status,
                        "error_details": detailed_error,
                        "message_count": len(session.messages),
                        "retry_possible": True
                    }
                    await self.db.end_session(session.session_id, error_result)
                    # Don't cleanup files yet - keep for potential retry
                    
                    return {
                        "status": "service_unavailable", 
                        "session_id": session.session_id,
                        "error": detailed_error,
                        "error_code": error_code,
                        "user_message": self._get_user_friendly_error_message(error_code),
                        "retry_possible": True
                    }
                else:
                    # Handle other error cases
                    await self.db.end_session(session.session_id, {"error": orchestrator_result.get("error", "Processing failed")})
                    await self._cleanup_session_files(session)
                    return {
                        "status": "error",
                        "session_id": session.session_id,
                        "error": orchestrator_result.get("error", "Processing failed")
                    }
            
        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            return {"error": str(e)}
    
    def _get_user_friendly_error_message(self, error_code: str) -> str:
        """Generate user-friendly error messages based on error code"""
        
        error_messages = {
            "AI_AGENT_CONNECTION_FAILED": "🔧 हमारे AI विश्लेषण सिस्टम में अस्थायी समस्या है। कृपया कुछ देर बाद पुनः प्रयास करें।",
            "AI_AGENT_TIMEOUT": "⏱️ AI विश्लेषण में सामान्य से अधिक समय लग रहा है। कृपया बाद में फिर से कोशिश करें।", 
            "AI_AGENT_HTTP_ERROR": "⚠️ AI सेवा में तकनीकी समस्या है। हमारी टीम इसे ठीक कर रही है।",
            "AI_AGENT_UNEXPECTED_ERROR": "❌ एक अप्रत्याशित त्रुटि हुई है। कृपया सहायता के लिए संपर्क करें।",
            "AI_AGENT_PROCESSING_FAILED": "🤖 AI विश्लेषण पूरा नहीं हो सका। कृपया अपना डेटा फिर से भेजें।"
        }
        
        return error_messages.get(error_code, "🔧 सिस्टम में तकनीकी समस्या है। कृपया बाद में पुनः प्रयास करें।")
    
    async def end_session_simple(self, telegram_user_id: int) -> bool:
        """End session without processing - just save and close"""
        
        try:
            # Get active session
            session = await self.get_active_session(telegram_user_id)
            if not session:
                return False
            
            # Remove from active sessions immediately
            if telegram_user_id in self.active_sessions:
                del self.active_sessions[telegram_user_id]
            
            # End session with simple status (no processing)
            simple_result = {
                "status": "ended_early_by_user",
                "message_count": len(session.messages),
                "session_duration": (datetime.now() - session.start_time).total_seconds(),
                "end_time": datetime.now().isoformat()
            }
            
            await self.db.end_session(session.session_id, simple_result)
            await self._cleanup_session_files(session)
            
            logger.info(f"Session ended early by user: {session.session_id} with {len(session.messages)} messages")
            return True
            
        except Exception as e:
            logger.error(f"Failed to end session simply: {e}")
            return False
    
    async def _prepare_session_for_processing(self, session: SessionLog) -> Dict[str, Any]:
        """Prepare session data for orchestrator"""
        
        messages = []
        for msg in session.messages:
            if msg.type == MessageType.TEXT:
                messages.append({
                    "type": "text",
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                })
            elif msg.type == MessageType.VOICE:
                messages.append({
                    "type": "voice", 
                    "file_path": msg.file_path,
                    "timestamp": msg.timestamp.isoformat()
                })
        
        # Get user language preference
        user_language = "hi"  # Default
        try:
            farmer = await self.db.get_farmer_by_telegram_id(session.telegram_user_id)
            if farmer and hasattr(farmer, 'language_preference') and farmer.language_preference:
                user_language = farmer.language_preference
        except Exception as e:
            logger.error(f"Failed to get user language: {e}")
        
        return {
            "session_id": session.session_id,
            "farmer_id": session.farmer_id,
            "start_time": session.start_time.isoformat(),
            "messages": messages,
            "user_language": user_language
        }
    
    async def _generate_mock_response(self, session: SessionLog) -> Dict[str, Any]:
        """Generate mock AI response for testing"""
        
        # Extract text content for mock analysis
        text_messages = [
            msg.content for msg in session.messages 
            if msg.type == MessageType.TEXT and msg.content
        ]
        voice_count = len([
            msg for msg in session.messages 
            if msg.type == MessageType.VOICE
        ])
        
        combined_text = " ".join(text_messages) if text_messages else ""
        
        # Mock eligibility analysis
        mock_schemes = []
        if any(word in combined_text.lower() for word in ["wheat", "rice", "crop"]):
            mock_schemes.extend(["PM-KISAN", "PMFBY"])
        if any(word in combined_text.lower() for word in ["small", "acre", "land"]):
            mock_schemes.append("PM-KISAN")
        if any(word in combined_text.lower() for word in ["loan", "credit", "money"]):
            mock_schemes.append("Kisan Credit Card")
        
        if not mock_schemes:
            mock_schemes = ["PM-KISAN"]  # Default
        
        # Generate recommendations using LLM
        recommendation_prompt = f"""Based on this farmer's session:
Text messages: {combined_text}
Voice messages: {voice_count}

Provide 3 practical recommendations for this farmer."""
        
        recommendations_text = await llm_client.generate_response(recommendation_prompt)
        recommendations = [
            line.strip() 
            for line in recommendations_text.split('\n') 
            if line.strip() and not line.strip().startswith('#')
        ][:3]
        
        return {
            "eligibility_status": "eligible",
            "eligible_schemes": mock_schemes,
            "recommendations": recommendations or [
                "Consider applying for PM-KISAN scheme",
                "Get soil health card for better crop planning", 
                "Explore crop insurance options"
            ],
            "confidence_score": 0.85,
            "processing_time": 2.3,
            "analysis": {
                "text_messages_analyzed": len(text_messages),
                "voice_messages_processed": voice_count,
                "total_messages": len(session.messages)
            }
        }
    
    async def _cleanup_session_files(self, session: SessionLog):
        """Clean up audio files after processing"""
        
        try:
            for message in session.messages:
                if message.type == MessageType.VOICE and message.file_path:
                    file_path = os.path.join(settings.upload_dir, message.file_path)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up file: {message.file_path}")
                        
        except Exception as e:
            logger.error(f"Failed to cleanup session files: {e}")
    
    async def cleanup_timeout_sessions(self):
        """Clean up sessions that have timed out"""
        
        try:
            cutoff_time = datetime.now() - timedelta(minutes=settings.session_timeout_minutes)
            
            # Find active sessions older than timeout
            timeout_sessions = []
            for user_id, session_id in list(self.active_sessions.items()):
                session = await self.db.get_session_by_id(session_id)
                if session and session.start_time < cutoff_time:
                    timeout_sessions.append((user_id, session))
            
            # Auto-process timeout sessions instead of just ending them
            for user_id, session in timeout_sessions:
                if session.messages:  # Only process if session has messages
                    logger.info(f"Auto-processing timeout session with {len(session.messages)} messages: {session.session_id}")
                    await self.end_session(user_id, auto_end=False)  # Process normally
                else:
                    logger.info(f"Auto-ended empty timeout session: {session.session_id}")
                    await self.end_session(user_id, auto_end=True)  # Just close empty session
            
            # Cleanup old sessions in database
            cleaned_count = await self.db.cleanup_old_sessions(24)
            
            return len(timeout_sessions) + cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup timeout sessions: {e}")
            return 0
    
    def is_session_active(self, telegram_user_id: int) -> bool:
        """Quick check if user has active session"""
        return telegram_user_id in self.active_sessions
    
    def _is_completion_indicator(self, message: str) -> bool:
        """Check if message indicates farmer is done explaining"""
        
        message_lower = message.lower()
        
        # Hindi completion indicators
        completion_phrases_hi = [
            "बस इतना ही", "यही है", "समाप्त", "खत्म", "पूरी बात हो गई",
            "बस यही था", "इतना ही काफी है", "अब क्या करना चाहिए",
            "क्या सलाह दोगे", "अब बताओ", "मेरी मदद करो", "सलाह दो"
        ]
        
        # English completion indicators  
        completion_phrases_en = [
            "that's all", "that's it", "done", "finished", "complete",
            "what should i do", "please help", "give advice", "suggest me",
            "what do you think", "any suggestions"
        ]
        
        # Bengali completion indicators
        completion_phrases_bn = [
            "বাস এতটুকুই", "এটাই", "শেষ", "সম্পূর্ণ", "এখন কি করব",
            "পরামর্শ দিন", "সাহায্য করুন", "কি করা উচিত"
        ]
        
        # Telugu completion indicators
        completion_phrases_te = [
            "అంతే", "ఇంతే", "పూర్తి", "ముగిసింది", "ఇప్పుడు ఏమి చేయాలి",
            "సలహా ఇవ్వండి", "సహాయం చేయండి"
        ]
        
        # Marathi completion indicators
        completion_phrases_mr = [
            "बस एवढेच", "हेच", "संपूर्ण", "आता काय करावे", "सल्ला द्या",
            "मदत करा", "काय सुचवाल"
        ]
        
        # Tamil completion indicators
        completion_phrases_ta = [
            "இவ்வளவுதான்", "முடிந்தது", "இது தான்", "இப்போது என்ன செய்வது",
            "ஆலோசனை கொடுங்கள்", "உதவி செய்யுங்கள்"
        ]
        
        # Gujarati completion indicators
        completion_phrases_gu = [
            "બસ આટલું જ", "આ જ છે", "સંપૂર્ણ", "હવે શું કરવું",
            "સલાહ આપો", "મદદ કરો"
        ]
        
        # Punjabi completion indicators
        completion_phrases_pa = [
            "ਬਸ ਇੰਨਾ ਹੀ", "ਇਹੀ ਹੈ", "ਪੂਰਾ", "ਹੁਣ ਕੀ ਕਰਨਾ",
            "ਸਲਾਹ ਦਿਓ", "ਮਦਦ ਕਰੋ"
        ]
        
        # Kannada completion indicators
        completion_phrases_kn = [
            "ಇಷ್ಟೇ", "ಇದು ಮಾತ್ರ", "ಪೂರ್ಣ", "ಈಗ ಏನು ಮಾಡಬೇಕು",
            "ಸಲಹೆ ಕೊಡಿ", "ಸಹಾಯ ಮಾಡಿ"
        ]
        
        # Malayalam completion indicators
        completion_phrases_ml = [
            "ഇത്രയും മതി", "ഇതാണ്", "പൂർത്തി", "ഇപ്പോൾ എന്ത് ചെയ്യണം",
            "ഉപദേശം തരൂ", "സഹായിക്കൂ"
        ]
        
        # Odia completion indicators
        completion_phrases_or = [
            "ବସ୍ ଏତିକି", "ଏହିତା", "ସମ୍ପୂର୍ଣ୍ଣ", "ଏବେ କଣ କରିବ",
            "ପରାମର୍ଶ ଦିଅ", "ସାହାଯ୍ୟ କର"
        ]
        
        # Assamese completion indicators
        completion_phrases_as = [
            "বাস ইমানেই", "এইটোৱেই", "সম্পূৰ্ণ", "এতিয়া কি কৰিম",
            "পৰামৰ্শ দিয়ক", "সহায় কৰক"
        ]
        
        # Urdu completion indicators
        completion_phrases_ur = [
            "بس اتنا ہی", "یہی ہے", "مکمل", "اب کیا کرنا چاہیے",
            "مشورہ دیں", "مدد کریں"
        ]
        
        # Rajasthani completion indicators
        completion_phrases_raj = [
            "बस इतनो ही", "यहीं है", "पूरो", "हुणे कांई करणो",
            "सलाह दो", "मदद करो"
        ]
        
        # Bhojpuri completion indicators
        completion_phrases_bho = [
            "बस एतना ही", "यहीं बा", "पूरा", "अब का करे के चाही",
            "सलाह दीं", "मदद करीं"
        ]
        
        # Combine all completion phrases
        all_phrases = (completion_phrases_hi + completion_phrases_en + 
                      completion_phrases_bn + completion_phrases_te + 
                      completion_phrases_mr + completion_phrases_ta +
                      completion_phrases_gu + completion_phrases_pa +
                      completion_phrases_kn + completion_phrases_ml +
                      completion_phrases_or + completion_phrases_as +
                      completion_phrases_ur + completion_phrases_raj +
                      completion_phrases_bho)
        
        return any(phrase in message_lower for phrase in all_phrases)
    
    async def _delayed_auto_process(self, telegram_user_id: int, delay_seconds: int):
        """Auto-process session after delay if still active"""
        
        try:
            await asyncio.sleep(delay_seconds)
            
            # Check if session is still active
            session = await self.get_active_session(telegram_user_id)
            if session and len(session.messages) >= 5:  # Only auto-process if at least 5 messages (was 3)
                logger.info(f"Auto-processing session after {delay_seconds}s delay: {session.session_id} with {len(session.messages)} messages")
                result = await self.end_session(telegram_user_id, auto_end=False)
                
                # Note: The bot will send results automatically through the normal flow
            else:
                if session:
                    logger.info(f"Skipping auto-process for session {session.session_id} - only {len(session.messages)} messages (need at least 5)")
                else:
                    logger.info(f"No active session found for user {telegram_user_id} during delayed auto-process")
                
        except Exception as e:
            logger.error(f"Failed in delayed auto-process: {e}")
    
    async def end_all_active_sessions_eod(self):
        """End all active sessions at End of Day (EOD)"""
        
        try:
            if not self.active_sessions:
                logger.info("No active sessions to end at EOD")
                return 0
            
            session_count = len(self.active_sessions)
            logger.info(f"Ending {session_count} active sessions at EOD")
            
            # Get a copy of active sessions to iterate over
            sessions_to_end = list(self.active_sessions.keys())
            
            ended_count = 0
            for telegram_user_id in sessions_to_end:
                try:
                    session = await self.get_active_session(telegram_user_id)
                    if session and session.messages:  # Only process sessions with messages
                        logger.info(f"EOD: Processing session {session.session_id} for user {telegram_user_id}")
                        result = await self.end_session(telegram_user_id, auto_end=False)
                        if result.get("status") in ["completed", "error"]:
                            ended_count += 1
                    elif session:
                        # Empty session, just end it without processing
                        logger.info(f"EOD: Ending empty session {session.session_id} for user {telegram_user_id}")
                        await self.end_session(telegram_user_id, auto_end=True)
                        ended_count += 1
                        
                except Exception as e:
                    logger.error(f"Error ending session for user {telegram_user_id} at EOD: {e}")
                    # Continue with other sessions
            
            logger.info(f"EOD processing completed: {ended_count}/{session_count} sessions ended successfully")
            return ended_count
            
        except Exception as e:
            logger.error(f"Failed to end sessions at EOD: {e}")
            return 0
    
    def calculate_seconds_until_eod(self) -> int:
        """Calculate seconds until End of Day (11:30 PM)"""
        from datetime import datetime, time
        import pytz
        
        # Use IST timezone for Indian farmers
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Set EOD time to 11:30 PM
        eod_time = time(23, 30)  # 11:30 PM
        eod_today = now.replace(hour=eod_time.hour, minute=eod_time.minute, second=0, microsecond=0)
        
        # If current time is past EOD, schedule for next day
        if now >= eod_today:
            from datetime import timedelta
            eod_today += timedelta(days=1)
        
        time_until_eod = eod_today - now
        return int(time_until_eod.total_seconds())
    
    async def schedule_eod_cleanup(self):
        """Schedule EOD cleanup for all active sessions"""
        
        try:
            seconds_until_eod = self.calculate_seconds_until_eod()
            hours_until_eod = seconds_until_eod / 3600
            
            logger.info(f"Scheduling EOD session cleanup in {hours_until_eod:.1f} hours")
            
            # Schedule the EOD cleanup
            asyncio.create_task(self._delayed_eod_cleanup(seconds_until_eod))
            
        except Exception as e:
            logger.error(f"Failed to schedule EOD cleanup: {e}")
    
    async def _delayed_eod_cleanup(self, delay_seconds: int):
        """Execute EOD cleanup after delay"""
        
        try:
            await asyncio.sleep(delay_seconds)
            
            logger.info("Executing scheduled EOD session cleanup")
            ended_count = await self.end_all_active_sessions_eod()
            
            # Schedule next day's EOD cleanup (24 hours from now)
            asyncio.create_task(self._delayed_eod_cleanup(24 * 3600))
            
        except Exception as e:
            logger.error(f"Failed in delayed EOD cleanup: {e}")

    async def _send_to_orchestrator(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send session data to orchestrator for processing"""
        
        import aiohttp
        import asyncio
        
        try:
            # Prepare payload for orchestrator
            payload = {
                "session_id": session_data["session_id"],
                "farmer_id": session_data["farmer_id"],
                "start_time": session_data["start_time"],
                "messages": session_data["messages"],
                "user_language": session_data.get("user_language", "hi")
            }
            
            timeout = aiohttp.ClientTimeout(total=settings.orchestrator_timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{settings.orchestrator_url}/process_session",
                    json=payload
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Orchestrator processing completed for session {session_data['session_id']}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Orchestrator returned error {response.status}: {error_text}")
                        return {
                            "status": "error",
                            "error": f"Orchestrator error: {response.status}"
                        }
                        
        except asyncio.TimeoutError:
            logger.error(f"Orchestrator request timeout for session {session_data['session_id']}")
            return {
                "status": "error",
                "error": "Service timeout"
            }
        except aiohttp.ClientError as e:
            logger.error(f"Orchestrator connection error: {e}")
            return {
                "status": "error", 
                "error": "Service unavailable"
            }
        except Exception as e:
            logger.error(f"Unexpected error sending to orchestrator: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

# Note: SessionManager instances should be created with database parameter 