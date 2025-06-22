import asyncio
import logging
from typing import Optional, Dict, Any, Callable
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

import threading
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

# --- Core Response Types ---
class BotResponse:
    def __init__(self, text: str, markup: Optional[InlineKeyboardMarkup] = None, 
                 parse_mode: str = ParseMode.MARKDOWN):
        self.text = text
        self.markup = markup
        self.parse_mode = parse_mode

class BotAction:
    SEND_MESSAGE = "send_message"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"
    ANSWER_CALLBACK = "answer_callback"

# --- Language Manager ---
class LanguageManager:
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
    def get_language_keyboard(cls) -> InlineKeyboardMarkup:
        keyboard = []
        langs = list(cls.LANGUAGES.items())
        
        # Create 2x6 grid
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
    def get_language_name(cls, lang_code: str) -> str:
        return cls.LANGUAGES.get(lang_code, {}).get("name", "English")

# --- Message Templates ---
class Messages:
    TEMPLATES = {
        "en": {
            "welcome_new": "🌾 *Welcome to Sanchalak, {name}!*\n\nYour AI-powered farming assistant for government schemes and agricultural advice.\n\nFirst, choose your language:",
            "welcome_back": "🌾 *Welcome back, {name}!*\n\nWhat would you like to do today?",
            "language_selected": "✅ *Language set to {language}*",
            "session_started": "🎙️ *Session Started*\n\nSession ID: `{session_id}`\n\nYou can now send messages, voice notes, or photos. Type /end_log when done.",
            "session_ended": "✅ *Session Ended*\n\nProcessing your session... Results will be sent shortly.",
            "no_active_session": "❌ No active session found.\n\nUse /start_log to begin a new session.",
            "session_already_active": "⚠️ You already have an active session.\n\nSession ID: `{session_id}`\n\nUse /end_log to end it first.",
            "error_generic": "❌ Something went wrong. Please try again.",
            "choose_language": "🌍 Choose Your Language",
            "start_session": "🎙️ Start Session",
            "help": "❓ Help",
            "status": "📊 Status",
            "change_language": "🌍 Language"
        },
        "hi": {
            "welcome_new": "🌾 *सञ्चालक में आपका स्वागत है, {name}!*\n\nसरकारी योजनाओं और कृषि सलाह के लिए आपका AI सहायक।\n\nपहले अपनी भाषा चुनें:",
            "welcome_back": "🌾 *वापस स्वागत है, {name}!*\n\nआज आप क्या करना चाहते हैं?",
            "language_selected": "✅ *भाषा {language} पर सेट की गई*",
            "session_started": "🎙️ *सेशन शुरू हुआ*\n\nसेशन ID: `{session_id}`\n\nअब आप संदेश, वॉयस नोट्स या फोटो भेज सकते हैं। समाप्त करने के लिए /end_log टाइप करें।",
            "session_ended": "✅ *सेशन समाप्त*\n\nआपका सेशन प्रोसेस हो रहा है... परिणाम जल्द भेजे जाएंगे।",
            "no_active_session": "❌ कोई सक्रिय सेशन नहीं मिला।\n\nनया सेशन शुरू करने के लिए /start_log का उपयोग करें।",
            "session_already_active": "⚠️ आपका पहले से ही एक सक्रिय सेशन है।\n\nसेशन ID: `{session_id}`\n\nपहले इसे समाप्त करने के लिए /end_log का उपयोग करें।",
            "error_generic": "❌ कुछ गलत हुआ। कृपया फिर से कोशिश करें।",
            "choose_language": "🌍 भाषा चुनें",
            "start_session": "🎙️ सेशन शुरू करें",
            "help": "❓ सहायता",
            "status": "📊 स्थिति",
            "change_language": "🌍 भाषा"
        }
    }
    
    @classmethod
    def get(cls, key: str, lang: str = "en", **kwargs) -> str:
        lang_code = "hi" if lang == "hindi" else "en"
        template = cls.TEMPLATES.get(lang_code, cls.TEMPLATES["en"]).get(key, cls.TEMPLATES["en"][key])
        try:
            return template.format(**kwargs)
        except:
            return template

# --- Core Bot Handlers ---
class BotHandlers:
    def __init__(self, db: Database, session_manager: SessionManager, user_state: UserStateManager):
        self.db = db
        self.session_manager = session_manager
        self.user_state = user_state
    
    async def safe_send_message(self, update: Update, response: BotResponse) -> bool:
        """Safely send message with fallback to plain text"""
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
            logger.warning(f"Markdown failed, trying plain text: {e}")
            try:
                plain_text = response.text.replace("*", "").replace("`", "").replace("_", "")
                if update.callback_query:
                    await update.callback_query.edit_message_text(plain_text, reply_markup=response.markup)
                else:
                    await update.message.reply_text(plain_text, reply_markup=response.markup)
                return True
            except Exception as e2:
                logger.error(f"Failed to send message: {e2}")
                return False
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        try:
            user = update.effective_user
            
            # Get or create user
            farmer = await self.user_state.get_or_create_user(user.id, user.first_name, user.username)
            user_context = await self.user_state.get_user_context(user.id)
            user_lang = await self.user_state.get_user_language(user.id)
            
            if user_context.get("registration_complete"):
                # Existing user - show main menu
                response = BotResponse(
                    Messages.get("welcome_back", user_lang, name=user.first_name),
                    self._get_main_menu_keyboard(user_lang)
                )
            else:
                # New user - show language selection
                response = BotResponse(
                    Messages.get("welcome_new", user_lang, name=user.first_name),
                    LanguageManager.get_language_keyboard()
                )
            
            await self.safe_send_message(update, response)
            
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            await self.safe_send_message(update, BotResponse(Messages.get("error_generic")))
    
    async def handle_start_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start_log command"""
        try:
            user = update.effective_user
            user_lang = await self.user_state.get_user_language(user.id)
            
            # Check for existing session
            if self.session_manager.is_session_active(user.id):
                active_session = await self.session_manager.get_active_session(user.id)
                response = BotResponse(
                    Messages.get("session_already_active", user_lang, session_id=active_session.session_id)
                )
            else:
                # Start new session
                farmer = await self.db.get_farmer_by_telegram_id(user.id)
                if not farmer:
                    response = BotResponse("❌ Please register first using /start")
                else:
                    session = await self.session_manager.start_session(user.id, farmer.farmer_id)
                    response = BotResponse(
                        Messages.get("session_started", user_lang, session_id=session.session_id)
                    )
            
            await self.safe_send_message(update, response)
            
        except Exception as e:
            logger.error(f"Error in start_log handler: {e}")
            await self.safe_send_message(update, BotResponse(Messages.get("error_generic")))
    
    async def handle_end_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /end_log command"""
        try:
            user = update.effective_user
            user_lang = await self.user_state.get_user_language(user.id)
            
            if not self.session_manager.is_session_active(user.id):
                response = BotResponse(Messages.get("no_active_session", user_lang))
            else:
                # End session
                result = await self.session_manager.end_session(user.id)
                response = BotResponse(Messages.get("session_ended", user_lang))
            
            await self.safe_send_message(update, response)
            
        except Exception as e:
            logger.error(f"Error in end_log handler: {e}")
            await self.safe_send_message(update, BotResponse(Messages.get("error_generic")))
    
    async def handle_language_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle language selection callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            lang_code = query.data.replace("lang_", "")
            user = query.from_user
            
            # Update language
            await self.user_state.update_user_language(user.id, lang_code)
            lang_name = LanguageManager.get_language_name(lang_code)
            
            # Send confirmation
            response = BotResponse(
                Messages.get("language_selected", lang_code, language=lang_name),
                self._get_main_menu_keyboard(lang_code)
            )
            
            await self.safe_send_message(update, response)
            
        except Exception as e:
            logger.error(f"Error in language selection: {e}")
            await self.safe_send_message(update, BotResponse(Messages.get("error_generic")))
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Route callback queries to appropriate handlers"""
        try:
            query = update.callback_query
            
            if query.data.startswith("lang_"):
                await self.handle_language_selection(update, context)
            elif query.data == "start_session":
                await self.handle_start_log(update, context)
            elif query.data == "show_languages":
                await query.answer()
                response = BotResponse(
                    Messages.get("choose_language"),
                    LanguageManager.get_language_keyboard()
                )
                await self.safe_send_message(update, response)
            else:
                await query.answer("Option not implemented yet")
                
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
    
    def _get_main_menu_keyboard(self, lang: str) -> InlineKeyboardMarkup:
        """Get main menu keyboard for user"""
        keyboard = [
            [InlineKeyboardButton(Messages.get("start_session", lang), callback_data="start_session")],
            [
                InlineKeyboardButton(Messages.get("help", lang), callback_data="help"),
                InlineKeyboardButton(Messages.get("status", lang), callback_data="status")
            ],
            [InlineKeyboardButton(Messages.get("change_language", lang), callback_data="show_languages")]
        ]
        return InlineKeyboardMarkup(keyboard)

# --- Main Bot Class ---
class SanchalakBot:
    def __init__(self):
        self.application = None
        self.db = Database()
        self.session_manager = SessionManager(self.db)
        self.user_state = UserStateManager(self.db)
        self.handlers = BotHandlers(self.db, self.session_manager, self.user_state)
    
    async def initialize(self):
        """Initialize bot"""
        try:
            logger.info("Initializing Sanchalak Bot...")
            
            # Initialize database
            await self.db.connect()
            logger.info("✅ Database connected")
            
            # Initialize application
            self.application = Application.builder().token(settings.telegram_bot_token).build()
            
            # Register handlers
            self._register_handlers()
            logger.info("✅ Handlers registered")
            
            # Set commands
            await self._set_bot_commands()
            logger.info("✅ Commands set")
            
            logger.info("🌾 Bot initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    def _register_handlers(self):
        """Register all handlers"""
        # Commands
        self.application.add_handler(CommandHandler("start", self.handlers.handle_start))
        self.application.add_handler(CommandHandler("start_log", self.handlers.handle_start_log))
        self.application.add_handler(CommandHandler("end_log", self.handlers.handle_end_log))
        
        # Callbacks
        self.application.add_handler(CallbackQueryHandler(self.handlers.handle_callback_query))
        
        # Messages (for active sessions)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        self.application.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        
        # Error handler
        self.application.add_error_handler(self._error_handler)
    
    async def _set_bot_commands(self):
        """Set bot commands"""
        commands = [
            BotCommand("start", "🌾 Start bot"),
            BotCommand("start_log", "📝 Start session"),
            BotCommand("end_log", "✅ End session")
        ]
        await self.application.bot.set_my_commands(commands)
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages during active session"""
        user_id = update.effective_user.id
        if self.session_manager.is_session_active(user_id):
            await self.session_manager.add_message(user_id, "text", update.message.text)
            await update.message.reply_text("✅ Message recorded")
        else:
            await update.message.reply_text("No active session. Use /start_log to begin.")
    
    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages during active session"""
        user_id = update.effective_user.id
        if self.session_manager.is_session_active(user_id):
            await self.session_manager.add_message(user_id, "voice", "voice_message")
            await update.message.reply_text("🎙️ Voice message recorded")
        else:
            await update.message.reply_text("No active session. Use /start_log to begin.")
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Error: {context.error}")
        if update and update.message:
            await update.message.reply_text("❌ Something went wrong. Please try again.")
    
    async def run(self):
        """Run the bot"""
        try:
            await self.initialize()
            
            logger.info("Starting bot polling...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            # Keep running
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping bot...")
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            await self.db.disconnect()

# Global bot instance
bot = SanchalakBot()

if __name__ == "__main__":
    # Start health check server
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()
    
    # Run bot
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}") 