"""
GraphQL Schema Example for PM-KISAN Conversational AI System

This demonstrates how GraphQL would solve the REST API complexity issues
in our conversational data collection system.

Key Benefits:
1. Single endpoint for all operations
2. Client specifies exactly what data it needs
3. Real-time subscriptions for chat
4. Better type safety and introspection
5. Unified schema for all conversation stages
"""

import strawberry
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from datetime import datetime

# GraphQL Types
@strawberry.enum
class ConversationStage(Enum):
    BASIC_INFO = "basic_info"
    FAMILY_MEMBERS = "family_members" 
    EXCLUSION_CRITERIA = "exclusion_criteria"
    SPECIAL_PROVISIONS = "special_provisions"
    COMPLETED = "completed"

@strawberry.enum
class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

@strawberry.type
class QuickOption:
    id: int
    text: str
    value: Optional[str] = None
    description: Optional[str] = None

@strawberry.type
class StageProgress:
    collected: int
    total: int
    percentage: float
    
    @strawberry.field
    def is_complete(self) -> bool:
        return self.collected >= self.total

@strawberry.type
class ConversationProgress:
    basic_info: StageProgress
    family_members: StageProgress
    exclusion_criteria: StageProgress
    special_provisions: StageProgress
    
    @strawberry.field
    def overall_percentage(self) -> float:
        total_collected = (
            self.basic_info.collected + 
            self.family_members.collected + 
            self.exclusion_criteria.collected + 
            self.special_provisions.collected
        )
        total_required = (
            self.basic_info.total + 
            self.family_members.total + 
            self.exclusion_criteria.total + 
            self.special_provisions.total
        )
        return (total_collected / total_required) * 100 if total_required > 0 else 0

@strawberry.type
class Message:
    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@strawberry.type
class FarmerData:
    basic_info: Dict[str, Any]
    family_members: List[Dict[str, Any]]
    exclusion_data: Dict[str, Any]
    special_provisions: Dict[str, Any]
    scheme_code: str
    completed_at: datetime

@strawberry.type
class ConversationSession:
    id: str
    scheme_code: str
    stage: ConversationStage
    created_at: datetime
    updated_at: datetime
    
    # Flexible data fetching - client chooses what to include
    @strawberry.field
    def messages(self, limit: Optional[int] = None) -> List[Message]:
        # Return conversation history
        pass
    
    @strawberry.field
    def progress(self) -> ConversationProgress:
        # Return detailed progress
        pass
    
    @strawberry.field
    def quick_options(self) -> Optional[List[QuickOption]]:
        # Return current quick options
        pass
    
    @strawberry.field
    def farmer_data(self) -> Optional[FarmerData]:
        # Only return if conversation is complete
        pass
    
    @strawberry.field
    def is_complete(self) -> bool:
        return self.stage == ConversationStage.COMPLETED

# Input Types
@strawberry.input
class StartConversationInput:
    scheme_code: str
    language: Optional[str] = "en"
    user_context: Optional[Dict[str, Any]] = None

@strawberry.input
class SendMessageInput:
    session_id: str
    content: str
    quick_option_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

# Mutations
@strawberry.type
class Mutation:
    
    @strawberry.mutation
    async def start_conversation(self, input: StartConversationInput) -> ConversationSession:
        """Start a new conversation - returns only what client requests"""
        # Implementation would initialize LangGraph engine
        pass
    
    @strawberry.mutation  
    async def send_message(self, input: SendMessageInput) -> Message:
        """Send message and get response - client chooses response fields"""
        # Implementation would process with LangGraph
        pass
    
    @strawberry.mutation
    async def restart_conversation(self, session_id: str) -> ConversationSession:
        """Restart conversation from beginning"""
        pass

# Queries  
@strawberry.type
class Query:
    
    @strawberry.field
    async def conversation(self, session_id: str) -> Optional[ConversationSession]:
        """Get conversation by ID - client specifies what fields to include"""
        pass
    
    @strawberry.field
    async def available_schemes(self) -> List[Dict[str, str]]:
        """Get list of available schemes"""
        pass

# Subscriptions for Real-time Chat
@strawberry.type
class Subscription:
    
    @strawberry.subscription
    async def message_stream(self, session_id: str) -> Message:
        """Real-time message stream for live chat"""
        # WebSocket-based real-time updates
        pass
    
    @strawberry.subscription
    async def progress_updates(self, session_id: str) -> ConversationProgress:
        """Real-time progress updates"""
        pass

# Schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation, 
    subscription=Subscription
)

"""
Example GraphQL Queries/Mutations:

1. Start Conversation (minimal response):
```graphql
mutation StartConversation($input: StartConversationInput!) {
  startConversation(input: $input) {
    id
    stage
    messages(limit: 1) {
      content
      role
    }
  }
}
```

2. Send Message (get only what's needed):
```graphql  
mutation SendMessage($input: SendMessageInput!) {
  sendMessage(input: $input) {
    content
    timestamp
  }
}
```

3. Get Progress (only progress data):
```graphql
query GetProgress($sessionId: String!) {
  conversation(sessionId: $sessionId) {
    progress {
      overallPercentage
      basicInfo {
        collected
        total
        isComplete
      }
    }
  }
}
```

4. Get Complete Data (when finished):
```graphql
query GetFarmerData($sessionId: String!) {
  conversation(sessionId: $sessionId) {
    isComplete
    farmerData {
      basicInfo
      familyMembers
      completedAt
    }
  }
}
```

5. Real-time Chat Subscription:
```graphql
subscription ChatStream($sessionId: String!) {
  messageStream(sessionId: $sessionId) {
    content
    role
    timestamp
  }
}
```

Benefits Over REST:
✅ Single endpoint (/graphql)
✅ Client specifies exact data needed
✅ Real-time subscriptions
✅ Type safety with schema
✅ No over-fetching/under-fetching  
✅ Better developer experience
✅ Introspection and tooling
✅ Unified conversation state
""" 