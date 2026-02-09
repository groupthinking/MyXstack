# Architecture Overview

## System Components

### 1. X API Client (`src/services/xapi.ts`)
- **Purpose**: Interface with X (Twitter) API
- **Responsibilities**:
  - Fetch mentions of the authenticated user
  - Retrieve complete conversation threads
  - Post replies to tweets
  - Search for tweets
  - Handle API authentication and rate limiting
- **Features**:
  - Simulation mode for testing without credentials
  - Error handling and retry logic
  - Response parsing and normalization

### 2. Grok AI Service (`src/services/grok.ts`)
- **Purpose**: Analyze mentions and decide actions using Grok AI
- **Responsibilities**:
  - Send context to Grok for analysis
  - Parse Grok's responses
  - Convert AI decisions into actionable tasks
- **Decision Types**:
  - **Reply**: Generate and post a response
  - **Search**: Query X for additional context
  - **Analyze**: Process information without posting
  - **Generate**: Create content based on context

### 3. Autonomous Agent (`src/services/agent.ts`)
- **Purpose**: Main orchestrator coordinating all components
- **Responsibilities**:
  - Poll for new mentions at regular intervals
  - Coordinate between X API and Grok AI
  - Execute actions based on AI decisions
  - Track processed mentions to avoid duplicates
  - Provide real-time monitoring feedback
- **Features**:
  - Configurable polling interval
  - Graceful shutdown handling
  - Statistics tracking
  - Error recovery

### 4. xMCP Server (`src/mcp/server.ts`)
- **Purpose**: Expose X API tools via Model Context Protocol
- **Responsibilities**:
  - Implement MCP server specification
  - Register available tools (fetch mentions, threads, post replies, search)
  - Handle tool invocation requests
  - Return standardized responses
- **Benefits**:
  - Standardized interface for AI models
  - Tool discovery and documentation
  - Type-safe communication
  - Extensible architecture

### 5. Configuration Manager (`src/services/config.ts`)
- **Purpose**: Load and validate environment configuration
- **Responsibilities**:
  - Load environment variables
  - Validate required credentials
  - Provide configuration to all components
  - Set sensible defaults

## Data Flow

```
┌────────────────────────────────────────────────────┐
│                   Main Process                      │
│                   (src/index.ts)                    │
└────────┬─────────────────────────────┬─────────────┘
         │                             │
         │                             │
         ▼                             ▼
┌──────────────────┐        ┌──────────────────────┐
│  Configuration   │        │    xMCP Server       │
│     Manager      │        │   (Background)       │
└────────┬─────────┘        └──────────────────────┘
         │                             │
         │                             │
         ▼                             ▼
┌──────────────────┐        ┌──────────────────────┐
│  Autonomous      │        │  X API Tools         │
│     Agent        │        │  (Standardized)      │
└────────┬─────────┘        └──────────────────────┘
         │
         │
         ▼
┌──────────────────────────────────────────────────┐
│              Processing Loop                      │
│  ┌────────────────────────────────────────────┐  │
│  │ 1. Poll X API for mentions                 │  │
│  │    ↓                                       │  │
│  │ 2. Fetch thread context                   │  │
│  │    ↓                                       │  │
│  │ 3. Send to Grok AI for analysis          │  │
│  │    ↓                                       │  │
│  │ 4. Receive action decision                │  │
│  │    ↓                                       │  │
│  │ 5. Execute action (reply/search/etc)      │  │
│  │    ↓                                       │  │
│  │ 6. Mark as processed                      │  │
│  │    ↓                                       │  │
│  │ 7. Wait for next poll interval            │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Polling vs. Webhooks
- **Choice**: Polling-based architecture
- **Rationale**: 
  - Simpler to implement and maintain
  - No need for public endpoint/server
  - Works with standard X API access
  - Configurable frequency
- **Future Enhancement**: Webhook support for real-time notifications

### 2. Simulation Mode
- **Choice**: Built-in simulation with mock data
- **Rationale**:
  - Test without API credentials
  - Demonstrate functionality
  - Safe development environment
  - No risk of accidental posts
- **Implementation**: Automatic fallback when credentials missing

### 3. MCP Server Integration
- **Choice**: Implement Model Context Protocol
- **Rationale**:
  - Standardized tool interface
  - Future-proof architecture
  - Easy to extend with new tools
  - Compatible with various AI models
- **Benefit**: Grok or other AI can invoke tools autonomously

### 4. TypeScript
- **Choice**: Full TypeScript implementation
- **Rationale**:
  - Type safety for API responses
  - Better IDE support
  - Catch errors at compile time
  - Improved maintainability

### 5. Stateless Processing
- **Choice**: No persistent storage, in-memory tracking only
- **Rationale**:
  - Simpler architecture
  - No database dependencies
  - Privacy-preserving
  - Easy to restart/recover
- **Trade-off**: Processed mentions reset on restart

## Security Considerations

1. **API Credentials**: Stored in environment variables, never in code
2. **Rate Limiting**: Respects X API rate limits
3. **Error Handling**: Graceful degradation on failures
4. **Input Validation**: All user inputs validated before processing
5. **Simulation Mode**: Safe testing without real API calls

## Extension Points

1. **New Action Types**:
   - Add to `AgentAction` type
   - Implement in `executeAction()` method
   - Update Grok prompts

2. **Additional MCP Tools**:
   - Add to `getTools()` in xMCP server
   - Implement handler in `CallToolRequestSchema`
   - Update X API client if needed

3. **Custom AI Models**:
   - Replace Grok service with alternative
   - Maintain same interface contract
   - Update configuration

4. **Multi-Account Support**:
   - Modify config to support multiple accounts
   - Run separate agent instances
   - Share MCP server if needed

## Performance Characteristics

- **Memory**: ~50MB baseline, grows with processed mentions
- **CPU**: Minimal, mostly I/O bound
- **Network**: Depends on polling frequency and mention volume
- **Scalability**: Single account per instance, can run multiple instances

## Monitoring and Observability

- **Console Logging**: Real-time activity feed
- **Statistics**: Track processed mentions and agent status
- **Error Reporting**: Comprehensive error logging
- **Graceful Shutdown**: Clean exit with final stats

## Future Enhancements

1. **Web Dashboard**: Monitor agent activity via web UI
2. **Webhook Support**: Real-time mention notifications
3. **Database Integration**: Persistent mention history
4. **Advanced Analytics**: Track engagement metrics
5. **Multi-Modal Support**: Handle images, videos, polls
6. **Conversation Memory**: Remember past interactions
7. **Sentiment Analysis**: Detect tone and emotion
8. **Rate Limit Management**: Smart backoff strategies
