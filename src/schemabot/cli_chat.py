#!/usr/bin/env python3
"""
CLI Chat Interface for Sanchalak Schemabot

This CLI interface allows you to test the EFR-integrated conversation system
with LM Studio as the LLM backend using the new intelligent conversation engine.
"""

import asyncio
import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from schemabot.core.conversation.langchain_engine import LangChainConversationEngine, ConversationState
from schemabot.core.scheme.efr_integration import EFRSchemeClient
from api.models.conversation import ConversationContext, MessageRole, ConversationStage
from langchain.schema import HumanMessage, AIMessage

class LMStudioClient:
    """Simple LM Studio client for CLI chat interface."""
    
    def __init__(self, base_url: str = "http://localhost:1234/v1", model_name: str = "google/gemma-3-4b"):
        """
        Initialize LM Studio client.
        
        Args:
            base_url: Base URL for LM Studio API
            model_name: Specific model to use (defaults to google/gemma-3-4b)
        """
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        
    async def chat_completion(self, messages: List[Dict[str, str]], 
                            temperature: float = 0.7, 
                            max_tokens: int = 512) -> Optional[str]:
        """
        Send chat completion request to LM Studio.
        
        Args:
            messages: List of message dictionaries with role and content
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text or None if failed
        """
        try:
            import requests
            
            # Ensure proper conversation format for google/gemma-3-4b
            formatted_messages = self._format_messages_for_gemma(messages)
            
            payload = {
                "model": self.model_name,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                print(f"❌ LM Studio API error: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ LM Studio connection failed: {e}")
            return None
    
    def _format_messages_for_gemma(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Format messages for google/gemma-3-4b model to ensure proper role alternation.
        
        Args:
            messages: Raw message list
            
        Returns:
            Properly formatted message list
        """
        formatted = []
        last_role = None
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            # Skip empty messages
            if not content.strip():
                continue
            
            # Ensure role alternation
            if role == last_role:
                # Combine with previous message if same role
                if formatted and formatted[-1]["role"] == role:
                    formatted[-1]["content"] += "\n" + content
                else:
                    formatted.append({"role": role, "content": content})
            else:
                formatted.append({"role": role, "content": content})
            
                last_role = role
        
        return formatted
    
    async def check_connection(self) -> bool:
        """Check if LM Studio is accessible and return available models."""
        try:
            import requests
            
            response = requests.get(f"{self.base_url}/models", timeout=10)
            if response.status_code == 200:
                models = response.json()
                available_models = [model["id"] for model in models.get("data", [])]
                return True, available_models
            return False, []
                
        except Exception as e:
            return False, []

class ChatSession:
    """Enhanced chat session with intelligent conversation engine."""
    
    def __init__(self, scheme_code: str, efr_api_url: str = "http://localhost:8001"):
        """
        Initialize chat session with intelligent conversation engine.
        
        Args:
            scheme_code: Scheme code (e.g., "pm-kisan")
            efr_api_url: URL for EFR database API
        """
        self.scheme_code = scheme_code
        self.efr_api_url = efr_api_url
        self.session_id = str(uuid.uuid4())
        
        # Initialize LangChain conversation engine
        self.conversation_engine = LangChainConversationEngine(efr_api_url)
        
        # Initialize LM Studio client
        self.llm_client = LMStudioClient()
        
        # Initialize conversation state
        self.conversation_state: Optional[ConversationState] = None
        self.chat_history: List[Any] = []
        
        # Session statistics
        self.stats = {
            "session_id": self.session_id,
            "scheme_code": scheme_code,
            "start_time": datetime.now(),
            "message_count": 0,
            "extraction_count": 0,
            "llm_calls": 0,
            "total_processing_time": 0.0
        }
        
    async def initialize(self) -> bool:
        """Initialize the chat session with intelligent conversation engine."""
        try:
            print("✅ LM Studio connected. Using model: google/gemma-3-4b")
        
        # Check LM Studio connection
            is_connected, available_models = await self.llm_client.check_connection()
            if not is_connected:
                print("❌ LM Studio not accessible")
                return False
        
            if available_models:
                print(f"   Other available models: {available_models}")
            
        # Check EFR database connection
            efr_client = EFRSchemeClient(self.efr_api_url)
            try:
                async with efr_client as client:
                    health_check = await client.health_check()
                    if health_check:
                        print("✅ EFR Database connected: EFR database is reachable")
                    else:
                        print("❌ EFR Database not accessible")
                        return False
            except Exception as e:
                print(f"❌ EFR Database connection failed: {e}")
                return False
        
            # Initialize conversation with LangChain engine
            initial_response, self.conversation_state = await self.conversation_engine.initialize_conversation(self.scheme_code)
            
            print("✅ Chat session initialized successfully")
            print()
            print("🎯 Ready to chat about pm-kisan!")
            print("=" * 50)
            
            # Display initial response
            print(f"🤖 Assistant: {initial_response}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize chat session: {e}")
            return False
    
    async def send_message(self, user_message: str) -> Optional[str]:
        """
        Send a message and get response using intelligent conversation engine.
        
        Args:
            user_message: User's message
            
        Returns:
            Assistant's response or None if failed
        """
        if not self.conversation_state:
            return "❌ Session not initialized. Please restart the chat."
        
        start_time = time.time()
        
        try:
            # Add user message to chat history
            self.chat_history.append(HumanMessage(content=user_message))
            
            # Process input with LangChain engine
            response, self.conversation_state = await self.conversation_engine.process_user_input(
                user_message, self.conversation_state
                    )
                    
            # Add assistant response to chat history
            self.chat_history.append(AIMessage(content=response))
            
            # Update statistics
            processing_time = time.time() - start_time
            self.stats["message_count"] += 1
            self.stats["extraction_count"] += 1
            self.stats["total_processing_time"] += processing_time
            
            # Display extraction results if available
            if self.conversation_state.collected_data:
                collected_count = len(self.conversation_state.collected_data)
                total_count = len(self.conversation_engine.required_fields)
                completion = self.conversation_engine.get_completion_percentage(self.conversation_state)
                
                print(f"📊 Progress: {collected_count}/{total_count} fields collected ({completion:.1f}%)")
                
                # Show recently extracted fields
                if collected_count > 0:
                    print("📋 Extracted so far:")
                    for field_name, value in list(self.conversation_state.collected_data.items())[-3:]:
                        print(f"   • {field_name}: {value}")
                    print()
            
            return response
                
        except Exception as e:
            processing_time = time.time() - start_time
            self.stats["total_processing_time"] += processing_time
            
            print(f"❌ Error processing message: {e}")
            return "I apologize, but I encountered an error processing your message. Please try again."
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics."""
        current_time = datetime.now()
        duration = current_time - self.stats["start_time"]
        
        stats = self.stats.copy()
        stats["duration_seconds"] = duration.total_seconds()
        stats["current_time"] = current_time.isoformat()
        
        if self.conversation_state:
            stats["collected_fields"] = len(self.conversation_state.collected_fields)
            stats["completion_percentage"] = self.intelligent_engine.get_completion_percentage(self.conversation_state)
            stats["conversation_stage"] = self.conversation_state.conversation_flow_stage
        
        return stats
    
    async def get_conversation_summary(self) -> str:
        """Get a summary of the conversation progress."""
        if not self.conversation_state:
            return "No conversation data available."
        
        return await self.conversation_engine.generate_summary(self.conversation_state)
    
    async def cleanup(self):
        """Clean up the chat session."""
        if hasattr(self, 'intelligent_engine'):
            # Clean up intelligent engine resources
            pass
        
        print("🧹 Chat session cleaned up")

class ChatCLI:
    """Main CLI interface for intelligent chat system."""
    
    def __init__(self):
        self.current_session: Optional[ChatSession] = None
        self.available_schemes = ["pm-kisan"]  # Hardcoded for now
    
    def print_banner(self):
        """Print application banner."""
        print("🚀 Sanchalak CLI Chat Interface")
        print("   Government Scheme Eligibility Assistant")
        print("   Powered by EFR Database + LM Studio (google/gemma-3-4b)")
        print("=" * 80)
    
    def print_help(self):
        """Print available commands."""
        print("Available commands:")
        print("  /start <scheme>  - Start a new conversation for a scheme")
        print("  /stats           - Show session statistics")
        print("  /summary         - Show conversation summary")
        print("  /schemes         - List available schemes")
        print("  /clear           - Clear the screen")
        print("  /help            - Show this help")
        print("  /quit or /exit   - Exit the application")
        print()
        print(f"Available schemes: {', '.join(self.available_schemes)}")
        print()
        print("Just type your message to chat!")
        print()
        print("💡 Tip: Start with '/start pm-kisan' to begin a conversation")
    
    async def start_scheme_conversation(self, scheme_code: str) -> bool:
        """Start a new conversation for a specific scheme."""
        if scheme_code not in self.available_schemes:
            print(f"❌ Unknown scheme: {scheme_code}")
            print(f"   Available schemes: {', '.join(self.available_schemes)}")
            return False
        
        print(f"🔄 Starting conversation for {scheme_code}...")
        print(f"🔗 Initializing chat session for scheme: {scheme_code}")
        
        # Clean up previous session
        if self.current_session:
            await self.current_session.cleanup()
        
        # Create new session
        self.current_session = ChatSession(scheme_code)
        
        # Initialize session
        success = await self.current_session.initialize()
        if not success:
            self.current_session = None
            return False
        
        return True
    
    async def run(self):
        """Run the interactive CLI chat interface."""
        self.print_banner()
        print()
        self.print_help()
        
        while True:
            try:
                if self.current_session:
                    user_input = input(f"[{self.current_session.scheme_code}] You: ").strip()
                else:
                    user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    command_parts = user_input[1:].split()
                    command = command_parts[0].lower()
                    
                    if command in ['quit', 'exit']:
                        if self.current_session:
                            await self.current_session.cleanup()
                        print("👋 Goodbye!")
                        break
                    
                    elif command == 'help':
                        self.print_help()
                    
                    elif command == 'clear':
                        import os
                        os.system('clear' if os.name == 'posix' else 'cls')
                        self.print_banner()
                    
                    elif command == 'schemes':
                        print(f"Available schemes: {', '.join(self.available_schemes)}")
                    
                    elif command == 'start':
                        if len(command_parts) < 2:
                            print("❌ Usage: /start <scheme>")
                            print(f"   Available schemes: {', '.join(self.available_schemes)}")
                        else:
                            scheme_code = command_parts[1]
                            await self.start_scheme_conversation(scheme_code)
                    
                    elif command == 'stats':
                        if self.current_session:
                            stats = self.current_session.get_session_stats()
                            print("📊 Session Statistics:")
                            print(f"   Session ID: {stats['session_id']}")
                            print(f"   Scheme: {stats['scheme_code']}")
                            print(f"   Duration: {stats['duration_seconds']:.1f}s")
                            print(f"   Messages: {stats['message_count']}")
                            print(f"   Extractions: {stats['extraction_count']}")
                            print(f"   Processing time: {stats['total_processing_time']:.2f}s")
                            if 'completion_percentage' in stats:
                                print(f"   Completion: {stats['completion_percentage']:.1f}%")
                                print(f"   Stage: {stats['conversation_stage']}")
                        else:
                            print("❌ No active session")
                    
                    elif command == 'summary':
                        if self.current_session:
                            summary = await self.current_session.get_conversation_summary()
                            print("📝 Conversation Summary:")
                            print(summary)
                        else:
                            print("❌ No active session")
                    
                    else:
                        print(f"❌ Unknown command: {command}")
                        print("   Type '/help' for available commands")
                
                    continue
                
                # Handle regular chat
                if not self.current_session:
                        print("❌ No active conversation. Start with '/start <scheme>'")
                        continue
                    
                # Send message to current session
                print("🤖 Using LangChain conversation engine")
                start_time = time.time()
                
                response = await self.current_session.send_message(user_input)
                response_time = time.time() - start_time
                print(f"⏱️  Response time: {response_time:.2f}s")
                if response:
                    print(f"🤖 Assistant: {response}")
            
            except KeyboardInterrupt:
                print("\n🛑 Interrupted by user")
                if self.current_session:
                    await self.current_session.cleanup()
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                continue

async def main():
    """Main entry point for the CLI chat interface."""
    cli = ChatCLI()
    await cli.run()

if __name__ == "__main__":
        asyncio.run(main())