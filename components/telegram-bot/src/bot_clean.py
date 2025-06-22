import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.constants import ParseMode

from config import settings
from database import Database
from session_manager import SessionManager
from user_state_manager import UserStateManager

from fastapi import FastAPI
import uvicorn

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Health Check Server ---
health_app = FastAPI()

@health_app.get("/health")
def read_health():
    return {"status": "healthy", "service": "Sanchalak Telegram Bot"}

def run_health_check_server():
    logger.info("Starting health check server on port 8080")
    uvicorn.run(health_app, host="0.0.0.0", port=8080, log_level="warning")

# --- Response Classes ---
class BotResponse:
    def __init__(self, text: str, markup: Optional[InlineKeyboardMarkup] = None, 
                 parse_mode: str = ParseMode.MARKDOWN):
        self.text = text
        self.markup = markup
        self.parse_mode = parse_mode

# --- Language System ---
class LanguageSystem:
    LANGUAGES = {
        "hindi": {"name": "हिंदी", "flag": "🇮🇳"},
        "english": {"name": "English", "flag": "🇺🇸"},
        "bengali": {"name": "বাংলা", "flag": "🇮🇳"},
        "telugu": {"name": "తెలుగు", "flag": "🇮🇳"},
        "marathi": {"name": "मराठी", "flag": "🇮🇳"},
        "tamil": {"name": "தமிழ்", "flag": "🇮🇳"},
        "gujarati": {"name": "ગુજરાતી", "flag": "🇮🇳"},
        "punjabi": {"name": "ਪੰਜਾਬੀ", "flag": "🇮🇳"},
        "kannada": {"name": "ಕನ್ನಡ", "flag": "🇮🇳"},
        "malayalam": {"name": "മലയാളം", "flag": "🇮🇳"},
        "odia": {"name": "ଓଡିଆ", "flag": "🇮🇳"},
        "assamese": {"name": "অসমীয়া", "flag": "🇮🇳"}
    }
    
    @classmethod
    def get_keyboard(cls) -> InlineKeyboardMarkup:
        keyboard = []
        langs = list(cls.LANGUAGES.items())
        
        for i in range(0, len(langs), 2):
            row = []
            for j in range(2):
                if i + j < len(langs):
                    lang_code, lang_info = langs[i + j]
                    btn_text = f"{lang_info['name']} {lang_info['flag']}"
                    row.append(InlineKeyboardButton(btn_text, callback_data=f"lang_{lang_code}"))
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    @classmethod
    def get_name(cls, lang_code: str) -> str:
        return cls.LANGUAGES.get(lang_code, {}).get("name", "English")

# --- Message Templates ---
class MessageTemplates:
    MESSAGES = {
        "en": {
            "welcome_new": "🌾 *Welcome to Sanchalak, {name}!*\n\nChoose your language to continue:",
            "welcome_back": "🌾 *Welcome back, {name}!*",
            "language_set": "✅ Language set to *{language}*",
            "session_started": "🎙️ *Session Started*\n\nSession ID: `{session_id}`\n\nSend messages, voice notes, or photos. Use /end_log when done.",
            "session_ended": "✅ *Session Ended*\n\nProcessing your data...",
            "no_session": "❌ No active session. Use /start_log to begin.",
            "session_exists": "⚠️ Session already active: `{session_id}`\n\nUse /end_log first.",
            "session_empty": "⚠️ Session was empty - no messages recorded.",
            "session_auto_ended": "ℹ️ Session was automatically ended.",
            "error": "❌ Something went wrong. Please try again.",
            "message_recorded": "✅ Message recorded",
            "voice_recorded": "🎙️ Voice recorded",
            "btn_start_session": "🎙️ Start Session",
            "btn_help": "❓ Help", 
            "btn_status": "📊 Status",
            "btn_language": "🌍 Language",
            "choose_language": "🌍 Choose Your Language"
        },
        "hi": {
            "welcome_new": "🌾 *सञ्चालक में स्वागत, {name}!*\n\nजारी रखने के लिए अपनी भाषा चुनें:",
            "welcome_back": "🌾 *वापस स्वागत, {name}!*",
            "language_set": "✅ भाषा *{language}* पर सेट की गई",
            "session_started": "🎙️ *सेशन शुरू*\n\nसेशन ID: `{session_id}`\n\nसंदेश, वॉयस या फोटो भेजें। समाप्त करने के लिए /end_log करें।",
            "session_ended": "✅ *सेशन समाप्त*\n\nआपका डेटा प्रोसेस हो रहा है...",
            "no_session": "❌ कोई सक्रिय सेशन नहीं। शुरू करने के लिए /start_log करें।",
            "session_exists": "⚠️ सेशन पहले से सक्रिय: `{session_id}`\n\nपहले /end_log करें।",
            "session_empty": "⚠️ सेशन खाली था - कोई संदेश रिकॉर्ड नहीं हुआ।",
            "session_auto_ended": "ℹ️ सेशन स्वचालित रूप से समाप्त हो गया।",
            "error": "❌ कुछ गलत हुआ। कृपया फिर कोशिश करें।",
            "message_recorded": "✅ संदेश रिकॉर्ड किया गया",
            "voice_recorded": "🎙️ वॉयस रिकॉर्ड किया गया",
            "btn_start_session": "🎙️ सेशन शुरू करें",
            "btn_help": "❓ सहायता",
            "btn_status": "📊 स्थिति", 
            "btn_language": "🌍 भाषा",
            "choose_language": "🌍 अपनी भाषा चुनें"
        }
    }
    
    @classmethod
    def get(cls, key: str, lang: str = "english", **kwargs) -> str:
        lang_code = "hi" if lang == "hindi" else "en"
        template = cls.MESSAGES.get(lang_code, cls.MESSAGES["en"]).get(key, cls.MESSAGES["en"][key])
        try:
            return template.format(**kwargs)
        except:
            return template

# --- Core Bot Logic ---
class BotCore:
    def __init__(self):
        self.db = Database()
        self.session_manager = SessionManager(self.db)
        self.user_state = UserStateManager(self.db)
    
    async def initialize(self):
        await self.db.connect()
        logger.info("✅ Bot core initialized")
    
    async def safe_send(self, update: Update, response: BotResponse) -> bool:
        """Safely send response with fallback"""
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    response.text, 
                    parse_mode=response.parse_mode,
                    reply_markup=response.markup
                )
            else:
                await update.message.reply_text(
                    response.text,
                    parse_mode=response.parse_mode,
                    reply_markup=response.markup
                )
            return True
        except Exception as e:
            logger.warning(f"Markdown failed: {e}")
            try:
                plain_text = response.text.replace("*", "").replace("`", "")
                if update.callback_query:
                    await update.callback_query.edit_message_text(plain_text, reply_markup=response.markup)
                else:
                    await update.message.reply_text(plain_text, reply_markup=response.markup)
                return True
            except Exception as e2:
                logger.error(f"Send failed: {e2}")
                return False
    
    def get_main_keyboard(self, lang: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(MessageTemplates.get("btn_start_session", lang), callback_data="start_session")],
            [
                InlineKeyboardButton(MessageTemplates.get("btn_help", lang), callback_data="help"),
                InlineKeyboardButton(MessageTemplates.get("btn_status", lang), callback_data="status")
            ],
            [InlineKeyboardButton(MessageTemplates.get("btn_language", lang), callback_data="show_languages")]
        ])

# --- Command Handlers ---
class CommandHandlers:
    def __init__(self, core: BotCore):
        self.core = core
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            farmer = await self.core.user_state.get_or_create_user(user.id, user.first_name, user.username)
            user_context = await self.core.user_state.get_user_context(user.id)
            user_lang = await self.core.user_state.get_user_language(user.id)
            
            if user_context.get("registration_complete"):
                response = BotResponse(
                    MessageTemplates.get("welcome_back", user_lang, name=user.first_name),
                    self.core.get_main_keyboard(user_lang)
                )
            else:
                response = BotResponse(
                    MessageTemplates.get("welcome_new", user_lang, name=user.first_name),
                    LanguageSystem.get_keyboard()
                )
            
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"Start error: {e}")
            await self.core.safe_send(update, BotResponse(MessageTemplates.get("error")))
    
    async def start_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            user_lang = await self.core.user_state.get_user_language(user.id)
            
            if self.core.session_manager.is_session_active(user.id):
                session = await self.core.session_manager.get_active_session(user.id)
                response = BotResponse(
                    MessageTemplates.get("session_exists", user_lang, session_id=session.session_id)
                )
            else:
                farmer = await self.core.db.get_farmer_by_telegram_id(user.id)
                if not farmer:
                    response = BotResponse("❌ Please register first using /start")
                else:
                    session = await self.core.session_manager.start_session(user.id, farmer.farmer_id)
                    response = BotResponse(
                        MessageTemplates.get("session_started", user_lang, session_id=session.session_id)
                    )
            
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"Start log error: {e}")
            await self.core.safe_send(update, BotResponse(MessageTemplates.get("error")))
    
    async def end_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            user_lang = await self.core.user_state.get_user_language(user.id)
            
            if not self.core.session_manager.is_session_active(user.id):
                response = BotResponse(MessageTemplates.get("no_session", user_lang))
            else:
                result = await self.core.session_manager.end_session(user.id)
                
                # Handle different end session results
                if "error" in result:
                    message = f"❌ Error: {result['error']}"
                elif result.get("status") == "queued_for_processing":
                    # System is down - user-friendly message
                    session_id = result.get("session_id", "unknown")
                    message_count = result.get("message_count", 0)
                    user_message = result.get("user_message", "")
                    message = f"✅ आपका सेशन सफलतापूर्वक लॉग किया गया है!\n\n📋 सेशन ID: `{session_id}`\n📊 संदेश: {message_count}\n\n{user_message}\n\n⏰ आपका अनुरोध सिस्टम वापस आने पर संसाधित होगा।"
                elif result.get("status") == "service_unavailable":
                    # AI services down but data saved
                    user_message = result.get("user_message", "")
                    session_id = result.get("session_id", "unknown")
                    message_count = result.get("message_count", 0)
                    message = f"✅ आपका सेशन सुरक्षित रूप से लॉग किया गया है!\n\n📋 सेशन ID: `{session_id}`\n📊 संदेश: {message_count}\n\n{user_message}"
                elif result.get("status") == "ended_early":
                    if result.get("message_count", 0) == 0:
                        message = MessageTemplates.get("session_empty", user_lang)
                    else:
                        message = MessageTemplates.get("session_auto_ended", user_lang)
                else:
                    # Success - normal processing
                    session_id = result.get("session_id", "unknown")
                    message_count = result.get("message_count", 0)
                    message = f"✅ आपका सेशन सफलतापूर्वक समाप्त और संसाधित किया गया है!\n\n📋 सेशन ID: `{session_id}`\n📊 संदेश: {message_count}\n\n🔍 आपका डेटा विश्लेषण के लिए भेजा गया है।"
                
                response = BotResponse(message)
            
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"End log error: {e}")
            await self.core.safe_send(update, BotResponse("❌ एक त्रुटि हुई। कृपया पुनः प्रयास करें।"))

# --- Callback Handlers ---
class CallbackHandlers:
    def __init__(self, core: BotCore):
        self.core = core
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()
            
            if query.data.startswith("lang_"):
                await self.handle_language_selection(update, context)
            elif query.data == "start_session":
                # Redirect to start_log
                await CommandHandlers(self.core).start_log(update, context)
            elif query.data == "show_languages":
                response = BotResponse(
                    MessageTemplates.get("choose_language"),
                    LanguageSystem.get_keyboard()
                )
                await self.core.safe_send(update, response)
            else:
                await query.answer("Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
    
    async def handle_language_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            lang_code = query.data.replace("lang_", "")
            user = query.from_user
            
            await self.core.user_state.update_user_language(user.id, lang_code)
            lang_name = LanguageSystem.get_name(lang_code)
            
            response = BotResponse(
                MessageTemplates.get("language_set", lang_code, language=lang_name),
                self.core.get_main_keyboard(lang_code)
            )
            
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"Language selection error: {e}")
            await self.core.safe_send(update, BotResponse(MessageTemplates.get("error")))

# --- Message Handlers ---
class MessageHandlers:
    def __init__(self, core: BotCore):
        self.core = core
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            
            if self.core.session_manager.is_session_active(user_id):
                await self.core.session_manager.add_message(user_id, "text", update.message.text)
                await update.message.reply_text(MessageTemplates.get("message_recorded", user_lang))
            else:
                await update.message.reply_text(MessageTemplates.get("no_session", user_lang))
        except Exception as e:
            logger.error(f"Text handler error: {e}")
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            
            if self.core.session_manager.is_session_active(user_id):
                await self.core.session_manager.add_message(user_id, "voice", "voice_message")
                await update.message.reply_text(MessageTemplates.get("voice_recorded", user_lang))
            else:
                await update.message.reply_text(MessageTemplates.get("no_session", user_lang))
        except Exception as e:
            logger.error(f"Voice handler error: {e}")

# --- Main Bot Application ---
class SanchalakBot:
    def __init__(self):
        self.application = None
        self.core = BotCore()
        self.commands = CommandHandlers(self.core)
        self.callbacks = CallbackHandlers(self.core)
        self.messages = MessageHandlers(self.core)
    
    async def initialize(self):
        try:
            logger.info("Initializing Sanchalak Bot...")
            
            await self.core.initialize()
            
            self.application = Application.builder().token(settings.telegram_bot_token).build()
            self._register_handlers()
            await self._set_commands()
            
            logger.info("🌾 Bot ready!")
            
        except Exception as e:
            logger.error(f"Init failed: {e}")
            raise
    
    def _register_handlers(self):
        # Commands
        self.application.add_handler(CommandHandler("start", self.commands.start))
        self.application.add_handler(CommandHandler("start_log", self.commands.start_log))
        self.application.add_handler(CommandHandler("end_log", self.commands.end_log))
        
        # Callbacks
        self.application.add_handler(CallbackQueryHandler(self.callbacks.handle_callback))
        
        # Messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.messages.handle_text))
        self.application.add_handler(MessageHandler(filters.VOICE, self.messages.handle_voice))
        
        # Errors
        self.application.add_error_handler(self._error_handler)
    
    async def _set_commands(self):
        commands = [
            BotCommand("start", "🌾 Start"),
            BotCommand("start_log", "📝 Start session"), 
            BotCommand("end_log", "✅ End session")
        ]
        await self.application.bot.set_my_commands(commands)
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Bot error: {context.error}")
        if update and update.message:
            await update.message.reply_text("❌ Error occurred. Please try again.")
    
    async def run(self):
        try:
            await self.initialize()
            
            logger.info("Starting polling...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Stopping...")
        except Exception as e:
            logger.error(f"Run error: {e}")
        finally:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            await self.core.db.disconnect()

# --- Entry Point ---
if __name__ == "__main__":
    # Start health server
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()
    
    # Run bot
    bot = SanchalakBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped") 