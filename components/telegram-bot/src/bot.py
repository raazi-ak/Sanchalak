import asyncio
import logging
from typing import Optional
import threading
import os
import html
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from config import settings
from database import Database
from session_manager import SessionManager
from user_state_manager import UserStateManager
from llm_client import llm_client

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

# llm_client is imported from llm_client module

# Markdown utilities
def safe_markdown_escape(text: str) -> str:
    """Safely escape markdown characters"""
    try:
        return escape_markdown(text, version=2)
    except:
        # Fallback: escape manually
        chars_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in chars_to_escape:
            text = text.replace(char, f'\\{char}')
        return text

def clean_text_for_telegram(text: str) -> str:
    """Clean text for telegram by removing problematic markdown"""
    return re.sub(r'[*_`\[\]()~>#+=|{}.!-]', '', text)

# Health Check Server
health_app = FastAPI()

@health_app.get("/health")
def read_health():
    return {"status": "healthy", "service": "Sanchalak Telegram Bot"}

def run_health_check_server():
    logger.info("Starting health check server on port 8080")
    uvicorn.run(health_app, host="0.0.0.0", port=8080, log_level="warning")

# Response Classes
class BotResponse:
    def __init__(self, text: str, markup: Optional[InlineKeyboardMarkup] = None, 
                 use_markdown: bool = False):
        self.text = text
        self.markup = markup
        self.use_markdown = use_markdown

# Language System
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
        "assamese": {"name": "অসমীয়া", "flag": "🇮🇳"},
        "urdu": {"name": "اردو", "flag": "🇮🇳"},
        "nepali": {"name": "नेपाली", "flag": "🇳🇵"}
    }
    
    @classmethod
    def get_keyboard(cls):
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
    def get_name(cls, lang_code: str):
        return cls.LANGUAGES.get(lang_code, {}).get("name", "English")

# Fixed Message Templates
# Import the proper Messages class from multilingual_messages
from multilingual_messages import messages

# Core Bot Logic
class BotCore:
    def __init__(self):
        self.db = Database()
        self.session_manager = SessionManager(self.db)
        self.user_state = UserStateManager(self.db)
    
    async def initialize(self):
        await self.db.connect()
        logger.info("✅ Bot core initialized")
    
    async def safe_send(self, update: Update, response: BotResponse):
        """Safely send response with better error handling"""
        try:
            # Try with HTML first (more reliable than markdown)
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    response.text, 
                    parse_mode=ParseMode.HTML if response.use_markdown else None,
                    reply_markup=response.markup
                )
            else:
                await update.message.reply_text(
                    response.text,
                    parse_mode=ParseMode.HTML if response.use_markdown else None,
                    reply_markup=response.markup
                )
            return True
        except Exception as e:
            logger.warning(f"Send with parse mode failed: {e}")
            try:
                # Fallback to plain text
                plain_text = clean_text_for_telegram(response.text)
                if update.callback_query:
                    await update.callback_query.edit_message_text(plain_text, reply_markup=response.markup)
                else:
                    await update.message.reply_text(plain_text, reply_markup=response.markup)
                return True
            except Exception as e2:
                logger.error(f"Send failed completely: {e2}")
                return False
    
    def get_main_keyboard(self, lang: str):
        return InlineKeyboardMarkup([
                    [InlineKeyboardButton(messages.get_message("START_SESSION_BUTTON", lang), callback_data="start_session")],
        [
            InlineKeyboardButton(messages.get_message("HELP_BUTTON", lang), callback_data="help"),
            InlineKeyboardButton("📊 Status", callback_data="status")
        ],
        [InlineKeyboardButton(messages.get_message("CHOOSE_LANGUAGE_BUTTON", lang), callback_data="show_languages")]
        ])

# Command Handlers
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
                    messages.get_message("WELCOME_BACK", user_lang, name=user.first_name),
                    self.core.get_main_keyboard(user_lang)
                )
            else:
                response = BotResponse(
                    messages.get_message("NEW_USER_WELCOME", user_lang, name=user.first_name),
                    LanguageSystem.get_keyboard()
                )
            
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"Start command error: {e}")
            await update.message.reply_text("❌ Something went wrong. Please try again.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            response = BotResponse(
                messages.get_message("HELP_MESSAGE", user_lang),
                self.core.get_main_keyboard(user_lang)
            )
            await self.core.safe_send(update, response)
        except Exception as e:
            logger.error(f"Help command error: {e}")
            await update.message.reply_text("❌ Something went wrong. Please try again.")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            user_context = await self.core.user_state.get_user_context(update.effective_user.id)
            active_session = await self.core.session_manager.get_active_session(update.effective_user.id)
            
            status_text = f"📊 *Status*\n\n"
            status_text += f"Language: {LanguageSystem.get_name(user_lang)}\n"
            status_text += f"Registration: {'✅ Complete' if user_context.get('registration_complete') else '⏳ Pending'}\n"
            status_text += f"Active Session: {'✅ Yes' if active_session else '❌ No'}"
            
            if active_session:
                status_text += f"\nSession ID: `{active_session.session_id}`"
            
            response = BotResponse(status_text, self.core.get_main_keyboard(user_lang))
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"Status command error: {e}")
            await update.message.reply_text("❌ Something went wrong. Please try again.")

    async def start_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            
            # Check for existing session
            active_session = await self.core.session_manager.get_active_session(user_id)
            if active_session:
                response = BotResponse(
                    messages.get_message("ERROR_ACTIVE_SESSION_EXISTS", user_lang, session_id=active_session.session_id, count=0),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
                return
            
            # Get user context to get farmer_id
            user_context = await self.core.user_state.get_user_context(user_id)
            
            # Start new session
            session = await self.core.session_manager.start_session(user_id, user_context["farmer_id"])
            response = BotResponse(
                messages.get_message("SESSION_STARTED", user_lang, session_id=session.session_id)
            )
            await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"Start log error: {e}")
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            await self.core.safe_send(update, BotResponse(messages.get_message("GENERIC_ERROR", user_lang)))

    async def end_log(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            
            # Check for active session
            active_session = await self.core.session_manager.get_active_session(user_id)
            if not active_session:
                response = BotResponse(
                    messages.get_message("ERROR_NO_ACTIVE_SESSION", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
                return
            
            # End session
            result = await self.core.session_manager.end_session(user_id)
            
            if result.get("status") == "service_unavailable":
                # AI service is down - show user-friendly error
                response = BotResponse(
                    messages.get_message("service_unavailable", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
            elif result.get("status") == "completed":
                # Normal successful completion
                response = BotResponse(
                    messages.get_message("SESSION_ENDED", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
            elif result.get("status") == "ended_early":
                # Session ended early (empty or auto-ended)
                if result.get("message_count", 0) == 0:
                    # Empty session
                    response = BotResponse(
                        messages.get_message("session_empty", user_lang),
                        self.core.get_main_keyboard(user_lang)
                    )
                else:
                    # Auto-ended session with messages
                    response = BotResponse(
                        messages.get_message("session_auto_ended", user_lang),
                        self.core.get_main_keyboard(user_lang)
                    )
                await self.core.safe_send(update, response)
            elif result.get("status") == "error":
                # Other errors
                response = BotResponse(
                    messages.get_message("session_end_error", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
            else:
                # Fallback for unknown status
                response = BotResponse(
                    messages.get_message("session_ended", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
            
        except Exception as e:
            logger.error(f"End log error: {e}")
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            await self.core.safe_send(update, BotResponse(messages.get_message("error", user_lang)))

# Callback Handlers
class CallbackHandlers:
    def __init__(self, core: BotCore):
        self.core = core
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            logger.info(f"Processing callback: {query.data}")
            if query.data.startswith("lang_"):
                await self.handle_language_selection(update, context)
            elif query.data == "show_languages":
                await self.show_language_menu(update, context)
            elif query.data == "help":
                await self.show_help(update, context)
            elif query.data == "status":
                await self.show_status(update, context)
            elif query.data == "start_session":
                await self.start_session_callback(update, context)
        except Exception as e:
            logger.error(f"Callback handler error in {query.data}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def handle_language_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        lang_code = query.data.replace("lang_", "")
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        try:
            # Update user language
            await self.core.user_state.update_user_language(user_id, lang_code)
            
            lang_name = LanguageSystem.get_name(lang_code)
            
            # Send confirmation
            confirmation_response = BotResponse(messages.get_message("language_set", lang_code, language=lang_name))
            await self.core.safe_send(update, confirmation_response)
            
            # Wait briefly for confirmation visibility
            await asyncio.sleep(1)
            
            # Send comprehensive welcome
            welcome_response = BotResponse(
                messages.get_message("language_welcome", lang_code, language=lang_name, name=user_name),
                self.core.get_main_keyboard(lang_code)
            )
            await self.core.safe_send(update, welcome_response)
            
        except Exception as e:
            logger.error(f"Language selection error: {e}")
            await query.edit_message_text("❌ Language update failed. Please try again.")
    
    async def show_language_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
        response = BotResponse(
            messages.get_message("choose_language", user_lang),
            LanguageSystem.get_keyboard()
        )
        await self.core.safe_send(update, response)
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
        response = BotResponse(
            messages.get_message("help_message", user_lang),
            self.core.get_main_keyboard(user_lang)
        )
        await self.core.safe_send(update, response)
    
    async def show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
        user_context = await self.core.user_state.get_user_context(update.effective_user.id)
        active_session = await self.core.session_manager.get_active_session(update.effective_user.id)
        
        status_text = f"📊 *Status*\n\n"
        status_text += f"Language: {LanguageSystem.get_name(user_lang)}\n"
        status_text += f"Registration: {'✅ Complete' if user_context.get('registration_complete') else '⏳ Pending'}\n"
        status_text += f"Active Session: {'✅ Yes' if active_session else '❌ No'}"
        
        if active_session:
            status_text += f"\nSession ID: `{active_session.session_id}`"
        
        response = BotResponse(status_text, self.core.get_main_keyboard(user_lang))
        await self.core.safe_send(update, response)
    
    async def start_session_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_lang = await self.core.user_state.get_user_language(user_id)
        
        # Check for existing session
        active_session = await self.core.session_manager.get_active_session(user_id)
        if active_session:
            response = BotResponse(
                messages.get_message("session_exists", user_lang, session_id=active_session.session_id),
                self.core.get_main_keyboard(user_lang)
            )
            await self.core.safe_send(update, response)
            return
        
        # Get user context to get farmer_id
        user_context = await self.core.user_state.get_user_context(user_id)
        
        # Start new session
        session = await self.core.session_manager.start_session(user_id, user_context["farmer_id"])
        response = BotResponse(
            messages.get_message("session_started", user_lang, session_id=session.session_id)
        )
        await self.core.safe_send(update, response)

# Message Handlers
class MessageHandlers:
    def __init__(self, core: BotCore):
        self.core = core
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            message_text = update.message.text
            
            # Check if user has active session
            active_session = await self.core.session_manager.get_active_session(user_id)
            
            if active_session:
                # Record message in session
                await self.core.session_manager.add_text_message(
                    user_id, 
                    message_text
                )
                await update.message.reply_text(messages.get_message("message_recorded", user_lang))
            else:
                # Generate AI response using LLM client
                user_context = await self.core.user_state.get_user_context(user_id)
                ai_response = await llm_client.generate_response(
                    message_text,
                    context={
                        "user_language": user_lang,
                        "farmer_info": user_context
                    }
                )
                
                # Send AI response
                await update.message.reply_text(ai_response)
                
        except Exception as e:
            logger.error(f"Text message error: {e}")
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            await update.message.reply_text(messages.get_message("error", user_lang))

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            
            # Check if user has active session
            active_session = await self.core.session_manager.get_active_session(user_id)
            
            if active_session:
                # Download voice file
                voice_file = await update.message.voice.get_file()
                file_data = await voice_file.download_as_bytearray()
                
                # Record voice message in session
                await self.core.session_manager.add_voice_message(
                    user_id, 
                    file_data,
                    "ogg"
                )
                await update.message.reply_text(messages.get_message("voice_recorded", user_lang))
            else:
                # Inform user to start a session for voice processing
                response = BotResponse(
                    messages.get_message("no_session", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
                
        except Exception as e:
            logger.error(f"Voice message error: {e}")
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            await update.message.reply_text(messages.get_message("error", user_lang))

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            user_lang = await self.core.user_state.get_user_language(user_id)
            
            # Check if user has active session
            active_session = await self.core.session_manager.get_active_session(user_id)
            
            if active_session:
                # Record photo caption as text message for now
                caption = update.message.caption or "📷 Photo uploaded"
                await self.core.session_manager.add_text_message(
                    user_id, 
                    caption
                )
                await update.message.reply_text(messages.get_message("photo_recorded", user_lang))
            else:
                # Inform user to start a session for photo processing
                response = BotResponse(
                    messages.get_message("no_session", user_lang),
                    self.core.get_main_keyboard(user_lang)
                )
                await self.core.safe_send(update, response)
                
        except Exception as e:
            logger.error(f"Photo message error: {e}")
            user_lang = await self.core.user_state.get_user_language(update.effective_user.id)
            await update.message.reply_text(messages.get_message("error", user_lang))

# Main Bot Class
class SanchalakBot:
    def __init__(self):
        self.core = BotCore()
        self.cmd_handlers = CommandHandlers(self.core)
        self.callback_handlers = CallbackHandlers(self.core)
        self.msg_handlers = MessageHandlers(self.core)
        self.application = None
    
    async def initialize(self):
        """Initialize bot and dependencies"""
        await self.core.initialize()
        
        # Build application
        self.application = Application.builder().token(settings.telegram_bot_token).build()
        
        # Register handlers
        self._register_handlers()
        
        # Set bot commands
        await self._set_commands()
        
        logger.info("✅ Sanchalak bot initialized successfully")
    
    def _register_handlers(self):
        """Register all message and command handlers"""
        # Commands
        self.application.add_handler(CommandHandler("start", self.cmd_handlers.start))
        self.application.add_handler(CommandHandler("help", self.cmd_handlers.help_command))
        self.application.add_handler(CommandHandler("status", self.cmd_handlers.status_command))
        self.application.add_handler(CommandHandler("start_log", self.cmd_handlers.start_log))
        self.application.add_handler(CommandHandler("end_log", self.cmd_handlers.end_log))
        
        # Callbacks
        self.application.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback))
        
        # Messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.msg_handlers.handle_text))
        self.application.add_handler(MessageHandler(filters.VOICE, self.msg_handlers.handle_voice))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.msg_handlers.handle_photo))
        
        # Error handler
        self.application.add_error_handler(self._error_handler)
    
    async def _set_commands(self):
        """Set bot commands for the menu"""
        commands = [
            BotCommand("start", "Register and start using Sanchalak"),
            BotCommand("help", "Get help and information"),
            BotCommand("start_log", "Start session for personalized advice"),
            BotCommand("end_log", "End current session"),
            BotCommand("status", "Check your status")
        ]
        await self.application.bot.set_my_commands(commands)
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Bot error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("❌ Something went wrong. Please try again.")
    
    async def run(self):
        """Run the bot"""
        logger.info("🚀 Starting bot polling...")
        
        # Start polling
        logger.info("✅ Bot is running... Press Ctrl+C to stop")
        
        # Initialize the application properly
        await self.application.initialize()
        await self.application.start()
        
        # Start the updater
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        # Keep running until stopped
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        finally:
            # Cleanup
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

# Main execution
def main():
    """Main entry point - synchronous"""
    # Start health check server in background
    health_thread = threading.Thread(target=run_health_check_server, daemon=True)
    health_thread.start()
    
    # Create and run bot
    bot = SanchalakBot()
    
    # Use asyncio.run for clean event loop management
    async def run_bot():
        try:
            await bot.initialize()
            await bot.run()
        except KeyboardInterrupt:
            logger.info("👋 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}")
            raise
    
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
