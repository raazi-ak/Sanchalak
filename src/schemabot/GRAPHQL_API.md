# GraphQL API Documentation - PM-KISAN Conversational AI System

## Overview

The PM-KISAN GraphQL API provides a modern, type-safe interface for conversational data collection. It replaces the complex REST API with a single endpoint that supports queries, mutations, and real-time subscriptions.

## Endpoints

- **GraphQL Endpoint**: `http://localhost:8003/graphql`
- **GraphQL Playground**: `http://localhost:8003/graphql` (GET request)
- **Health Check**: `http://localhost:8003/health`
- **API Documentation**: `http://localhost:8003/docs`

## Key Features

✅ **Single Endpoint**: All operations through `/graphql`
✅ **Real-time Subscriptions**: WebSocket-based live chat
✅ **Precise Data Fetching**: Client specifies exactly what data to fetch
✅ **Type Safety**: Strong schema validation
✅ **LangGraph Integration**: AI-powered conversations
✅ **Progress Tracking**: Rich progress information

## GraphQL Schema

### Types

#### ConversationSession
```graphql
type ConversationSession {
  id: String!
  schemeCode: String!
  stage: Stage!
  createdAt: DateTime!
  updatedAt: DateTime!
  isComplete: Boolean!
  
  # Flexible data fetching
  messages(limit: Int): [Message!]!
  progress: ConversationProgress!
  quickOptions: [QuickOption!]
  farmerData: FarmerData
}
```

#### Message
```graphql
type Message {
  id: String!
  role: MessageRole!
  content: String!
  timestamp: DateTime!
}
```

#### ConversationProgress
```graphql
type ConversationProgress {
  overallPercentage: Float!
  basicInfo: StageProgress!
  familyMembers: StageProgress!
  exclusionCriteria: StageProgress!
  specialProvisions: StageProgress!
}
```

#### StageProgress
```graphql
type StageProgress {
  collected: Int!
  total: Int!
  percentage: Float!
  isComplete: Boolean!
}
```

### Enums

```graphql
enum Stage {
  BASIC_INFO
  FAMILY_MEMBERS
  EXCLUSION_CRITERIA
  SPECIAL_PROVISIONS
  COMPLETED
}

enum MessageRole {
  USER
  ASSISTANT
  SYSTEM
}
```

## Operations

### 1. Start Conversation

**Mutation:**
```graphql
mutation StartConversation($input: StartConversationInput!) {
  startConversation(input: $input) {
    id
    stage
    messages(limit: 1) {
      content
      role
      timestamp
    }
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

**Variables:**
```json
{
  "input": {
    "schemeCode": "pm-kisan",
    "language": "en"
  }
}
```

**Response:**
```json
{
  "data": {
    "startConversation": {
      "id": "fc73b913-0b47-4abc-9049-84caaba17d4e",
      "stage": "BASIC_INFO",
      "messages": [
        {
          "content": "🚀 Welcome to the PM-KISAN application assistant!...",
          "role": "ASSISTANT",
          "timestamp": "2025-07-20T12:08:11.659787"
        }
      ],
      "progress": {
        "overallPercentage": 0,
        "basicInfo": {
          "collected": 0,
          "total": 17,
          "percentage": 0,
          "isComplete": false
        }
      }
    }
  }
}
```

### 2. Send Message

**Mutation:**
```graphql
mutation SendMessage($input: SendMessageInput!) {
  sendMessage(input: $input) {
    id
    content
    role
    timestamp
  }
}
```

**Variables:**
```json
{
  "input": {
    "sessionId": "fc73b913-0b47-4abc-9049-84caaba17d4e",
    "content": "My name is John Smith"
  }
}
```

**Response:**
```json
{
  "data": {
    "sendMessage": {
      "id": "c1e57bdb-859c-4f23-9aeb-798e0d4f0a11",
      "content": "✅ Input is valid and name has been extracted..\n\nCould you please tell me your age?",
      "role": "ASSISTANT",
      "timestamp": "2025-07-20T12:08:11.659787"
    }
  }
}
```

### 3. Get Conversation State

**Query:**
```graphql
query GetConversation($sessionId: String!) {
  conversation(sessionId: $sessionId) {
    id
    stage
    isComplete
    progress {
      overallPercentage
      basicInfo {
        collected
        total
        percentage
        isComplete
      }
      familyMembers {
        collected
        total
        percentage
        isComplete
      }
      exclusionCriteria {
        collected
        total
        percentage
        isComplete
      }
      specialProvisions {
        collected
        total
        percentage
        isComplete
      }
    }
    farmerData {
      basicInfo
      familyMembers
      exclusionData
      specialProvisions
      schemeCode
      completedAt
    }
  }
}
```

### 4. Real-time Chat Subscription

**Subscription:**
```graphql
subscription ChatStream($sessionId: String!) {
  messageStream(sessionId: $sessionId) {
    id
    content
    role
    timestamp
  }
}
```

**Usage with WebSocket:**
```javascript
// Using graphql-ws or similar WebSocket client
const client = new Client({
  url: 'ws://localhost:8003/graphql',
});

client.subscribe(
  {
    query: `
      subscription ChatStream($sessionId: String!) {
        messageStream(sessionId: $sessionId) {
          content
          role
          timestamp
        }
      }
    `,
    variables: { sessionId: 'your-session-id' }
  },
  {
    next: (message) => {
      console.log('New message:', message);
    },
  }
);
```

### 5. Get Available Schemes

**Query:**
```graphql
query GetAvailableSchemes {
  availableSchemes {
    scheme_code
    name
    description
  }
}
```

## Client Integration

### JavaScript/TypeScript (Frontend)

```javascript
import { request, gql } from 'graphql-request';

const endpoint = 'http://localhost:8003/graphql';

// Start conversation
const startConversation = async (schemeCode) => {
  const mutation = gql`
    mutation StartConversation($input: StartConversationInput!) {
      startConversation(input: $input) {
        id
        stage
        messages(limit: 1) {
          content
        }
      }
    }
  `;
  
  return await request(endpoint, mutation, {
    input: { schemeCode }
  });
};

// Send message
const sendMessage = async (sessionId, content) => {
  const mutation = gql`
    mutation SendMessage($input: SendMessageInput!) {
      sendMessage(input: $input) {
        content
        timestamp
      }
    }
  `;
  
  return await request(endpoint, mutation, {
    input: { sessionId, content }
  });
};
```

### Python

```python
import requests

def graphql_request(query, variables=None):
    response = requests.post(
        'http://localhost:8003/graphql',
        json={'query': query, 'variables': variables}
    )
    return response.json()

# Start conversation
start_query = """
mutation StartConversation($input: StartConversationInput!) {
  startConversation(input: $input) {
    id
    stage
    messages(limit: 1) {
      content
    }
  }
}
"""

result = graphql_request(start_query, {
    'input': {'schemeCode': 'pm-kisan'}
})
```

### cURL Examples

```bash
# Start conversation
curl -X POST http://localhost:8003/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { startConversation(input: {schemeCode: \"pm-kisan\"}) { id stage messages(limit: 1) { content } } }"
  }'

# Send message
curl -X POST http://localhost:8003/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { sendMessage(input: {sessionId: \"your-session-id\", content: \"My name is John\"}) { content timestamp } }"
  }'

# Get progress
curl -X POST http://localhost:8003/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { conversation(sessionId: \"your-session-id\") { progress { overallPercentage } } }"
  }'
```

## Benefits Over REST

| Feature | REST API | GraphQL API |
|---------|----------|-------------|
| Endpoints | Multiple (`/start`, `/chat`, `/status`) | Single (`/graphql`) |
| Data Fetching | Over-fetching/Under-fetching | Precise data fetching |
| Real-time | Polling required | WebSocket subscriptions |
| Type Safety | Manual validation | Schema validation |
| Documentation | Manual docs | Self-documenting |
| Caching | Complex | Built-in query caching |
| Versioning | URL versioning | Schema evolution |

## Error Handling

GraphQL returns errors in a standardized format:

```json
{
  "data": null,
  "errors": [
    {
      "message": "Session not found. Please start a new conversation.",
      "locations": [{"line": 2, "column": 3}],
      "path": ["sendMessage"]
    }
  ]
}
```

## Performance Considerations

1. **Query Complexity**: GraphQL queries are analyzed for complexity
2. **Rate Limiting**: Applied at the operation level
3. **Caching**: Automatic query result caching
4. **Batching**: Multiple operations in single request

## Development Tools

1. **GraphQL Playground**: Interactive query builder at `/graphql`
2. **Schema Introspection**: Built-in schema exploration
3. **Query Validation**: Real-time query validation
4. **Performance Metrics**: Built-in query performance tracking

## Migration from REST

If migrating from the old REST API:

| Old REST Endpoint | New GraphQL Operation |
|-------------------|----------------------|
| `GET /start/{scheme}` | `mutation { startConversation(...) }` |
| `POST /chat` | `mutation { sendMessage(...) }` |
| `GET /sessions/{id}/status` | `query { conversation(...) { progress } }` |
| `GET /sessions/{id}/farmer-data` | `query { conversation(...) { farmerData } }` |

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure frontend origin is allowed
2. **WebSocket Connection Failed**: Check firewall settings
3. **Session Not Found**: Use session ID returned by `startConversation`
4. **Invalid Query**: Use GraphQL Playground to validate syntax

### Debug Mode

Enable debug logging by setting environment variable:
```bash
export GRAPHQL_DEBUG=true
```

This enables detailed logging of:
- Query execution times
- LangGraph conversation state
- Session management
- WebSocket connections 