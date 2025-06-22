#!/usr/bin/env python3
"""
Multilingual message system for Sanchalak Telegram Bot
Provides translations for all user-facing messages from locale files.
"""

import json
import os
from typing import Dict, Any

class MultilingualMessages:
    """Provides multilingual support for bot messages by loading them from JSON files."""
    
    # This dictionary is the single source of truth for supported languages.
    # The keys are user-facing language names (in their native script), 
    # and values are language codes which correspond to the JSON file names 
    # in the 'locales' directory.
    LANGUAGE_CODES = {
        "English": "en", 
        "हिंदी": "hi",
        "বাংলা": "bn",
        "తెలుగు": "te",
        "मराठी": "mr",
        "தமிழ்": "ta",
        "ગુજરાતી": "gu",
        "ਪੰਜਾਬੀ": "pa",
        "ಕನ್ನಡ": "kn",
        "മലയാളം": "ml",
        "ଓଡ଼ିଆ": "or",
        "অসমীয়া": "as",
        "اردو": "ur",
        "नेपाली": "ne",
        "संस्कृतम्": "sa"
    }
    
    _messages: Dict[str, Dict[str, Any]] = {}

    def __init__(self, locale_dir: str = "locales"):
        self._locale_dir = locale_dir
        self._load_messages()

    def _load_messages(self):
        # Load English first as a fallback
        en_path = os.path.join(self._locale_dir, "en.json")
        try:
            with open(en_path, "r", encoding="utf-8") as f:
                self._messages["en"] = json.load(f)
        except FileNotFoundError:
            print(f"Error: English language file (en.json) not found in {self._locale_dir}. This is the fallback language.")
            self._messages["en"] = {} # Empty dict to avoid errors

        for lang_code in self.LANGUAGE_CODES.values():
            if lang_code == "en":
                continue
            
            file_path = os.path.join(self._locale_dir, f"{lang_code}.json")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self._messages[lang_code] = json.load(f)
            except FileNotFoundError:
                print(f"Warning: Language file for code '{lang_code}' not found. Will use English fallback.")
    
    def get_message(self, key: str, lang_code: str = "en", **kwargs) -> str:
        """
        Retrieves a message by key for the specified language code.
        Falls back to English if the language or key is not found.
        Formats the message with provided kwargs.
        """
        lang_code = lang_code.lower()
        
        # Default to English if language not supported
        lang_messages = self._messages.get(lang_code)
        
        # Fallback to English if language is not found
        if lang_messages is None:
            lang_messages = self._messages.get("en", {})
            
        message = lang_messages.get(key)
        
        # Fallback to English if key is not found in the target language
        if message is None:
            message = self._messages.get("en", {}).get(key, f"_{key}_")
        
        try:
            return message.format(**kwargs) if kwargs else message
        except KeyError as e:
            print(f"Error formatting message '{key}' for language '{lang_code}': Missing key {e}")
            # Provide a fallback message that shows the key and the missing placeholder
            return f"Error: Missing data for {key} ({e})"
    
    def get_language_code(self, language_name: str) -> str:
        """Returns the language code for a given language name."""
        # This is not efficient, but LANGUAGE_CODES is small.
        for name, code in self.LANGUAGE_CODES.items():
            if name.lower() == language_name.lower():
                return code
        return "en" # default to english
    
    def get_language_name(self, lang_code: str) -> str:
        """Returns the language name for a given language code."""
        for name, code in self.LANGUAGE_CODES.items():
            if code == lang_code.lower():
                return name
        return "English" # default to English

# Instantiate the message provider
messages = MultilingualMessages() 