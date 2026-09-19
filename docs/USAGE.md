# Usage Examples

## Basic Usage

### Starting the Agent

```bash
# With real credentials
npm start

# Development mode (rebuilds on changes)
npm run dev
```

### Expected Output

```
═══════════════════════════════════════════════════
  MyXstack - Autonomous AI Agent on X (Twitter)
═══════════════════════════════════════════════════

📋 Loading configuration...
✅ Configuration loaded

🔧 Initializing X API client...
✅ X API client ready

🌐 Initializing xMCP server...
✅ xMCP server ready

🚀 Initializing autonomous agent...
🤖 Starting Autonomous Agent...
👤 Monitoring account: @yourusername
⏱️  Polling interval: 30000ms

✅ Agent is now running. Monitoring for mentions...

⏳ [2:30:15 PM] No new mentions
⏳ [2:30:45 PM] No new mentions
```

## Real-World Scenarios

### Scenario 1: Answering Questions

**Someone mentions you:**
```
@yourusername What's your take on the latest AI developments?
```

**Agent output:**
```
📬 [2:31:15 PM] Found 1 new mention(s)!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Processing Mention:
   From: @curious_user
   Text: "@yourusername What's your take on the latest AI developments?"
   ID: 1234567890

🧵 Fetching thread context...
   Thread has 1 posts

🤖 Analyzing with Grok AI...
   Action: REPLY
   Confidence: 92.5%
   Reasoning: User asked for opinion on AI developments, best action is to provide an informed response

⚡ Executing action...
   ✓ Reply posted successfully
   📝 "Great question! Recent AI developments have been remarkable, especially in areas like multimodal understanding and reasoning. The rapid progress in LLMs has opened new possibilities for autonomous systems. What specific aspect interests you most?"

✅ Mention processed successfully!
```

### Scenario 2: Research Requests

**Someone asks for information:**
```
@yourusername Can you find recent tweets about quantum computing?
```

**Agent output:**
```
📬 [2:35:20 PM] Found 1 new mention(s)!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Processing Mention:
   From: @research_bot
   Text: "@yourusername Can you find recent tweets about quantum computing?"
   ID: 1234567891

🧵 Fetching thread context...
   Thread has 1 posts

🤖 Analyzing with Grok AI...
   Action: SEARCH
   Confidence: 88.0%
   Reasoning: User requested search for specific topic, best action is to search and summarize

⚡ Executing action...
   ✓ Search completed: found 10 results
   🔍 Query: "quantum computing recent breakthrough"
   
   [Posting summary of findings...]
   ✓ Reply posted successfully
   📝 "I found several interesting tweets about quantum computing! Here are the highlights: [summary of top results]. Would you like me to dive deeper into any particular aspect?"

✅ Mention processed successfully!
```

### Scenario 3: Thread Participation

**Someone mentions you in an ongoing discussion:**
```
Thread:
- @user1: "The future of AI is fascinating!"
- @user2: "Absolutely! What about autonomous agents?"
- @user3: "@yourusername what do you think?"
```

**Agent output:**
```
📬 [2:40:30 PM] Found 1 new mention(s)!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Processing Mention:
   From: @user3
   Text: "@yourusername what do you think?"
   ID: 1234567892

🧵 Fetching thread context...
   Thread has 4 posts

🤖 Analyzing with Grok AI...
   Action: REPLY
   Confidence: 90.0%
   Reasoning: User invited opinion in ongoing discussion about autonomous agents, context shows genuine interest

⚡ Executing action...
   ✓ Reply posted successfully
   📝 "Autonomous agents are indeed the next frontier! I'm an example of one - I can monitor, analyze, and respond to mentions automatically. The key is combining context awareness with intelligent decision-making. The possibilities for automation and assistance are endless!"

✅ Mention processed successfully!
```

## Advanced Configuration

### Custom Polling Interval

For high-traffic accounts, reduce the polling interval:

```env
# Check every 10 seconds
POLLING_INTERVAL_MS=10000
```

For low-traffic or rate-limit concerns, increase it:

```env
# Check every 2 minutes
POLLING_INTERVAL_MS=120000
```

### Testing with Simulation Mode

Test the system without credentials:

1. **Remove API keys from .env:**
   ```env
   X_USERNAME=testuser
   # Leave X_BEARER_TOKEN and XAI_API_KEY empty
   ```

2. **Start the agent:**
   ```bash
   npm start
   ```

3. **Observe simulated behavior:**
   ```
   ⚠️  Running in simulation mode - X API calls will be mocked
   ⚠️  Running in simulation mode - Grok AI calls will be mocked
   
   📨 Simulated: Found 1 mention(s)
   🧵 Simulated: Fetched thread with 2 posts
   🤖 Simulated Grok Analysis
   📤 Simulated: Would post reply...
   ```

## Integration Examples

### Using as a Library

You can import and use components programmatically:

```typescript
import { loadConfig } from './services/config.js';
import { XAPIClient } from './services/xapi.js';
import { AutonomousAgent } from './services/agent.js';

async function main() {
  const config = loadConfig();
  const xClient = new XAPIClient(config.xApiConfig);
  const agent = new AutonomousAgent(config, xClient);
  
  await agent.start();
  
  // Get statistics
  setTimeout(() => {
    const stats = agent.getStats();
    console.log(`Processed ${stats.processedMentions} mentions`);
  }, 60000);
}

main();
```

### Direct X API Client Usage

```typescript
import { XAPIClient } from './services/xapi.js';
import { loadConfig } from './services/config.js';

const config = loadConfig();
const client = new XAPIClient(config.xApiConfig);

// Fetch mentions
const mentions = await client.fetchMentions('yourusername');
console.log(`Found ${mentions.length} mentions`);

// Fetch a thread
const thread = await client.fetchThread('1234567890');
console.log(`Thread has ${thread?.replies.length} replies`);

// Post a reply
const success = await client.postReply('1234567890', 'Thanks for the mention!');
console.log(`Reply posted: ${success}`);
```

### Using Grok Service Independently

```typescript
import { GrokService } from './services/grok.js';

const grok = new GrokService(process.env.XAI_API_KEY!);

const analysis = await grok.analyzeAndDecide(
  'Can you help me understand this?',
  threadContext
);

console.log(`Recommended action: ${analysis.action.type}`);
console.log(`Confidence: ${analysis.confidence}`);
console.log(`Reasoning: ${analysis.explanation}`);
```

## Troubleshooting

### No mentions detected

**Problem:** Agent runs but never finds mentions.

**Solutions:**
1. Check that `X_USERNAME` matches your actual X username
2. Verify API credentials are correct
3. Ensure someone has actually mentioned you
4. Check X API rate limits

### API errors

**Problem:** Getting 401 or 403 errors.

**Solutions:**
1. Verify all API credentials in `.env`
2. Check that API keys have proper permissions
3. Ensure OAuth 1.0a is enabled for posting
4. Verify bearer token is valid

### Rate limiting

**Problem:** Getting rate limit errors.

**Solutions:**
1. Increase `POLLING_INTERVAL_MS`
2. Reduce mention volume
3. Use X API v2 premium tier
4. Implement exponential backoff (future enhancement)

### Build errors

**Problem:** TypeScript compilation fails.

**Solutions:**
1. Delete `node_modules` and `package-lock.json`
2. Run `npm install` again
3. Ensure Node.js version is 18+
4. Check for conflicting global TypeScript installations

## Best Practices

1. **Start in simulation mode** to understand behavior
2. **Use conservative polling intervals** to respect rate limits
3. **Monitor console output** for errors and unusual behavior
4. **Test with test accounts** before using on main account
5. **Review generated replies** in simulation mode first
6. **Set up proper error alerting** for production use
7. **Keep credentials secure** - never commit `.env` file
8. **Regularly update dependencies** for security patches

## Stopping the Agent

Press `Ctrl+C` to stop gracefully:

```
^C
🔄 Received shutdown signal...
🛑 Stopping agent...
📊 Final stats: 15 mentions processed
👋 Goodbye!
```
