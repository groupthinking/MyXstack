# GitHub Copilot Instructions for MyXstack

## Repository Overview

MyXstack is an autonomous AI agent system for X (Twitter) that uses Grok AI via the xMCP (Model Context Protocol) server. The agent monitors mentions, analyzes conversations using AI, and autonomously responds with context-aware actions.

## Technology Stack

- **Language**: TypeScript (ES2022)
- **Runtime**: Node.js 18+
- **AI Service**: Grok (xAI API)
- **Protocol**: Model Context Protocol (MCP)
- **APIs**: X (Twitter) API v2
- **Build Tool**: TypeScript Compiler (tsc)

## Project Structure

```
src/
├── index.ts              # Main entry point
├── examples.ts           # Usage examples
├── types/                # TypeScript type definitions
├── services/
│   ├── config.ts        # Configuration management
│   ├── xapi.ts          # X API client
│   ├── grok.ts          # Grok AI service
│   └── agent.ts         # Autonomous agent orchestrator
└── mcp/
    └── server.ts        # xMCP server implementation
```

## Coding Standards

### TypeScript

- **Strict Mode**: Always maintain strict TypeScript compilation
- **Types**: Use explicit types; avoid `any` except when absolutely necessary
- **Async/Await**: Prefer async/await over raw promises
- **Error Handling**: Always wrap API calls in try-catch blocks
- **Null Safety**: Use optional chaining (`?.`) and nullish coalescing (`??`)
- **ES Modules**: Use ES module syntax (`import`/`export`), not CommonJS

### Naming Conventions

- **Classes**: PascalCase (e.g., `XAPIClient`, `AutonomousAgent`)
- **Interfaces/Types**: PascalCase (e.g., `AgentConfig`, `XApiResponse`)
- **Functions/Methods**: camelCase (e.g., `fetchMentions`, `analyzeAndDecide`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_POLLING_INTERVAL`)
- **Files**: kebab-case for multi-word (e.g., `x-api.ts`) or camelCase for single word

### Code Organization

- **Single Responsibility**: Each service/class should have one clear purpose
- **Interface Segregation**: Define clear interfaces for external dependencies
- **Dependency Injection**: Pass dependencies through constructors
- **Configuration**: All environment variables should be loaded via `config.ts`
- **Simulation Mode**: Support simulation/mock mode for all external API calls

### Documentation

- **Public Methods**: Add JSDoc comments explaining purpose, parameters, and return values
- **Complex Logic**: Add inline comments for non-obvious algorithms
- **Type Definitions**: Document interfaces with descriptions of each field
- **Examples**: Include usage examples in JSDoc for key functions

## Build and Development

### Building

```bash
npm run build       # Compile TypeScript to dist/
npm run clean       # Remove dist/ directory
```

### Running

```bash
npm start          # Run compiled code
npm run dev        # Build and run
npm run examples   # Run usage examples
```

### Environment Variables

Required environment variables (see `.env.example`):
- `X_USERNAME`: X account username to monitor
- `X_BEARER_TOKEN`: X API bearer token for read operations
- `X_CONSUMER_KEY`, `X_CONSUMER_SECRET`: OAuth 1.0a credentials
- `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`: OAuth user tokens
- `XAI_API_KEY`: xAI/Grok API key
- `POLLING_INTERVAL_MS`: Optional, defaults to 30000ms

**IMPORTANT**: Never commit credentials or `.env` files. Always use environment variables.

## Testing Strategy

### Current Status
- No formal test suite yet
- Manual testing via simulation mode
- Integration testing with real APIs in development

### When Adding Tests
- Place tests in `src/__tests__/` directory
- Use a standard testing framework (e.g., Jest, Vitest)
- Write unit tests for services
- Mock external API calls
- Test error handling paths

## API Integration Patterns

### X API Client (`xapi.ts`)

When adding new X API features:
1. Add method to `XAPIClient` class
2. Include simulation/mock mode support
3. Handle rate limiting gracefully
4. Parse and normalize response data
5. Add proper error handling with descriptive messages

Example pattern:
```typescript
async newFeature(param: string): Promise<Result> {
  if (this.config.simulation) {
    return this.mockResult();
  }
  
  try {
    const response = await fetch(/* API call */);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('❌ Error:', error);
    throw error;
  }
}
```

### Grok AI Service (`grok.ts`)

When modifying AI analysis:
1. Keep prompts clear and specific
2. Provide sufficient context to the AI
3. Parse responses defensively
4. Include fallback behavior for unexpected responses
5. Support simulation mode with realistic mock data

### MCP Server (`mcp/server.ts`)

When adding new MCP tools:
1. Register tool in `getTools()` method
2. Add handler in tool invocation logic
3. Follow MCP specification for tool schema
4. Document tool capabilities in description
5. Return structured, type-safe results

## Security Best Practices

### API Keys and Credentials
- **Never hardcode**: All credentials must be in environment variables
- **Validation**: Validate all credentials at startup
- **Logging**: Never log credentials or tokens
- **Error Messages**: Don't expose credentials in error messages

### Input Validation
- **User Input**: Sanitize all user-generated content before processing
- **API Responses**: Validate structure of all API responses
- **Type Checking**: Use TypeScript types to catch errors at compile time

### Rate Limiting
- **Respect Limits**: Honor X API rate limits
- **Graceful Degradation**: Handle rate limit errors gracefully
- **Backoff**: Implement exponential backoff for retries

### Data Privacy
- **Minimal Storage**: Don't persist sensitive user data
- **In-Memory Only**: Current design uses in-memory tracking
- **No Logs**: Don't log private conversation content

## Error Handling

### Pattern to Follow
```typescript
try {
  // Operation
} catch (error) {
  console.error('❌ Descriptive error message:', error);
  // Graceful fallback or re-throw if critical
  if (isCritical) throw error;
  return fallbackValue;
}
```

### Logging Conventions
- ✅ Success: Green checkmark
- ❌ Error: Red X
- ⚠️  Warning: Yellow warning
- 📬 Mention: Envelope
- 🤖 AI Activity: Robot
- 🧵 Thread: Thread emoji
- ⏳ Waiting: Hourglass

## Agent Architecture

### Main Components

1. **Configuration Manager** (`config.ts`): Centralized configuration loading
2. **X API Client** (`xapi.ts`): Interface to X API
3. **Grok Service** (`grok.ts`): AI analysis and decision-making
4. **Autonomous Agent** (`agent.ts`): Main orchestration loop
5. **xMCP Server** (`mcp/server.ts`): MCP protocol implementation

### Processing Flow

```
Poll for mentions → Fetch thread context → 
Analyze with Grok → Make decision → 
Execute action → Mark as processed → Wait → Repeat
```

### Adding New Action Types

1. Add to `AgentActionType` enum in `types/index.ts`
2. Update `AgentAction` interface if needed
3. Implement handler in `agent.ts` `executeAction()` method
4. Update Grok prompts to recognize new action type
5. Add simulation mode support
6. Document in ARCHITECTURE.md

## Performance Considerations

- **Memory**: Keep processed mentions map bounded
- **CPU**: Minimize blocking operations
- **Network**: Batch requests when possible
- **Polling**: Use appropriate intervals (default: 30s)

## Deployment

### Environment Setup
1. Clone repository
2. Run `npm install`
3. Copy `.env.example` to `.env`
4. Configure all required environment variables
5. Run `npm run build`
6. Run `npm start`

### Production Considerations
- Use process manager (PM2, systemd) for restarts
- Monitor logs for errors
- Set up alerts for failures
- Consider containerization (Docker)
- Use proper logging service
- Implement health checks

## Common Tasks

### Adding a New X API Endpoint
1. Add method to `XAPIClient` in `src/services/xapi.ts`
2. Include simulation mode mock
3. Update types in `src/types/index.ts` if needed
4. Add error handling
5. Document in USAGE.md

### Modifying Agent Behavior
1. Update decision logic in `GrokService` (`src/services/grok.ts`)
2. Adjust prompts to guide AI behavior
3. Test with simulation mode first
4. Update ARCHITECTURE.md with changes

### Adding New MCP Tools
1. Define tool schema in `mcp/server.ts` `getTools()`
2. Implement tool handler in `CallToolRequestSchema` handler
3. Test with MCP client
4. Document tool capabilities

## Documentation Updates

When making changes, update relevant documentation:
- **ARCHITECTURE.md**: System design and component changes
- **USAGE.md**: Usage examples and new features
- **README.md**: Setup instructions and overview
- **DEPLOYMENT.md**: Deployment-related changes
- **.env.example**: New environment variables

## Git Workflow

- **Branches**: Create feature branches from `main`
- **Commits**: Use descriptive commit messages
- **PRs**: Include description of changes and testing performed
- **Code Review**: All changes should be reviewed

## AI Agent Development Principles

1. **Context Awareness**: Always provide full conversation context to AI
2. **Explainability**: Log AI reasoning and confidence levels
3. **Safety**: Include guardrails and review before posting
4. **Autonomy**: Design for minimal human intervention
5. **Adaptability**: Make behavior configurable and tunable
6. **Monitoring**: Track agent actions and outcomes
7. **Graceful Degradation**: Handle failures without crashing

## Future Enhancements to Consider

When extending the codebase:
- Database integration for persistent state
- Web dashboard for monitoring
- Webhook support for real-time notifications
- Multi-account support
- Advanced analytics and metrics
- Conversation memory/context retention
- Multi-modal support (images, videos)
- Integration with other AI models
- Advanced rate limit management

## Questions or Issues?

Refer to:
- **ARCHITECTURE.md** for system design
- **USAGE.md** for usage examples
- **DEPLOYMENT.md** for deployment guides
- **README.md** for quick start

## Copilot Specific Guidance

When suggesting code:
1. **Follow existing patterns** in the codebase
2. **Maintain type safety** - use TypeScript properly
3. **Include error handling** for all external calls
4. **Support simulation mode** for testing
5. **Add appropriate logging** with emojis per convention
6. **Update documentation** when changing behavior
7. **Consider rate limits** for X API operations
8. **Preserve security** - never expose credentials
9. **Think about scale** - avoid unbounded memory growth
10. **Test thoroughly** - include simulation mode testing
