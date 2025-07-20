"""
GraphQL Server for PM-KISAN Conversational AI System

This replaces the complex REST API with a clean GraphQL interface.
Provides single endpoint, real-time subscriptions, and precise data fetching.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from schemabot.api.graphql_schema import schema

# Create FastAPI app
app = FastAPI(
    title="PM-KISAN GraphQL Chat API",
    description="""
    ## GraphQL API for PM-KISAN Conversational AI System
    
    This API provides a modern GraphQL interface for conversational data collection.
    
    ### Features
    - 🚀 **Single Endpoint**: All operations through /graphql
    - 🔄 **Real-time Subscriptions**: WebSocket-based live chat
    - 📊 **Precise Data Fetching**: Client specifies exactly what data to fetch
    - 🤖 **AI-Powered Conversations**: LangGraph-powered natural language processing
    - 🛡️ **Type Safety**: Strong typing with schema validation
    
    ### Endpoints
    - **POST /graphql**: Main GraphQL endpoint for queries and mutations
    - **WebSocket /graphql**: GraphQL subscriptions for real-time updates
    - **GET /graphql**: GraphQL Playground (development)
    
    ### Example Operations
    
    #### Start Conversation:
    ```graphql
    mutation StartConversation {
      startConversation(input: {schemeCode: "pm-kisan"}) {
        id
        stage
        messages(limit: 1) {
          content
          role
        }
        progress {
          overallPercentage
        }
      }
    }
    ```
    
    #### Send Message:
    ```graphql
    mutation SendMessage {
      sendMessage(input: {
        sessionId: "your-session-id"
        content: "My name is Rajesh Kumar"
      }) {
        content
        role
        timestamp
      }
    }
    ```
    
    #### Real-time Chat Subscription:
    ```graphql
    subscription ChatStream {
      messageStream(sessionId: "your-session-id") {
        content
        role
        timestamp
      }
    }
    ```
    
    #### Get Progress:
    ```graphql
    query GetProgress {
      conversation(sessionId: "your-session-id") {
        progress {
          overallPercentage
          basicInfo {
            collected
            total
            percentage
            isComplete
          }
        }
      }
    }
    ```
    """,
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create GraphQL router with subscriptions support
graphql_router = GraphQLRouter(
    schema,
    subscription_protocols=[
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
        GRAPHQL_WS_PROTOCOL,
    ],
    # Enable GraphQL Playground in development
    graphiql=True,
)

# Mount GraphQL router
app.include_router(graphql_router, prefix="/graphql")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "PM-KISAN GraphQL Chat API",
        "version": "1.0.0",
        "features": {
            "graphql_queries": True,
            "graphql_mutations": True,
            "graphql_subscriptions": True,
            "real_time_chat": True,
            "langgraph_integration": True,
        }
    }

# Root endpoint redirect to GraphQL Playground
@app.get("/")
async def root():
    """Root endpoint - redirect to GraphQL Playground"""
    return {
        "message": "PM-KISAN GraphQL Chat API",
        "graphql_endpoint": "/graphql",
        "playground": "/graphql",
        "health": "/health",
        "docs": "/docs",
        "example_operations": {
            "start_conversation": """
mutation StartConversation {
  startConversation(input: {schemeCode: "pm-kisan"}) {
    id
    stage
    messages(limit: 1) {
      content
    }
  }
}""",
            "send_message": """
mutation SendMessage {
  sendMessage(input: {
    sessionId: "your-session-id"
    content: "My name is Rajesh"
  }) {
    content
    timestamp
  }
}""",
            "real_time_subscription": """
subscription ChatStream {
  messageStream(sessionId: "your-session-id") {
    content
    role
    timestamp
  }
}"""
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003) 