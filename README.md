# MyXstack 🤖✨

**Autonomous AI Agent System on X (Twitter)**

MyXstack is an intelligent, autonomous AI agent that monitors your X (Twitter) account for mentions, analyzes them using Grok AI, and takes appropriate actions—all without manual intervention. Experience the future of social media automation with a "tag and watch" system where the agent executes live in threads.

## 🌟 Features

- **🔔 Automatic Mention Detection**: Continuously monitors your X account for new mentions and tags
- **🧵 Thread Context Analysis**: Fetches complete conversation threads for better context understanding
- **🤖 Grok AI Integration**: Uses xAI's Grok for intelligent analysis and decision-making
- **⚡ Autonomous Actions**: Automatically replies, searches, or generates content based on context
- **🌉 xMCP Server Bridge**: Standardized Model Context Protocol server exposing X API tools
- **🎭 Simulation Mode**: Test the system without real API credentials
- **📊 Real-time Monitoring**: Live console output showing agent decisions and actions

## 🏗️ Architecture

```
┌─────────────────┐
│  X (Twitter)    │
│  Mentions       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  X API Client   │◄────►│  xMCP Server │
└────────┬────────┘      └──────────────┘
         │                       ▲
         ▼                       │
┌─────────────────┐             │
│  Autonomous     │             │
│  Agent          │             │
│  Orchestrator   │             │
└────────┬────────┘             │
         │                       │
         ▼                       │
┌─────────────────┐             │
│  Grok AI        │─────────────┘
│  Service        │
└─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm
- X (Twitter) API credentials (optional for simulation mode)
- xAI API key for Grok (optional for simulation mode)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/groupthinking/MyXstack.git
   cd MyXstack
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Build the project**
   ```bash
   npm run build
   ```

5. **Start the agent**
   ```bash
   npm start
   ```

## ⚙️ Configuration

Create a `.env` file based on `.env.example`:

```env
# X (Twitter) API Credentials
X_API_KEY=your_api_key_here
X_API_SECRET=your_api_secret_here
X_ACCESS_TOKEN=your_access_token_here
X_ACCESS_TOKEN_SECRET=your_access_token_secret_here
X_BEARER_TOKEN=your_bearer_token_here

# X Account Settings
X_USERNAME=your_twitter_username

# Grok/xAI Settings
XAI_API_KEY=your_xai_api_key_here

# Agent Settings
POLLING_INTERVAL_MS=30000  # Check for mentions every 30 seconds
MAX_RETRIES=3
```

### Getting API Credentials

#### X (Twitter) API
1. Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a new project and app
3. Generate API keys and access tokens
4. Enable OAuth 1.0a for posting

#### xAI (Grok)
1. Visit [xAI Console](https://console.x.ai/)
2. Sign up and create an API key
3. Copy your API key to the `.env` file

## 🎮 Usage

### Running in Production Mode

With real API credentials configured:

```bash
npm start
```

The agent will:
1. Monitor your X account for mentions
2. Fetch conversation context
3. Analyze with Grok AI
4. Take autonomous actions (reply, search, analyze)

### Running in Simulation Mode

Test without real credentials (leave `X_BEARER_TOKEN` and `XAI_API_KEY` empty):

```bash
npm start
```

The agent will use simulated data to demonstrate functionality.

### Development Mode

```bash
npm run dev
```

## 📖 How It Works

1. **Mention Detection**: The agent polls the X API every 30 seconds (configurable) to check for new mentions

2. **Context Fetching**: When a mention is found, the agent fetches the complete thread/conversation for context

3. **Grok Analysis**: The mention and thread context are sent to Grok AI, which decides:
   - Should we reply? (and with what content)
   - Should we search for more information?
   - Should we just analyze without taking action?

4. **Action Execution**: Based on Grok's decision, the agent:
   - Posts a reply to the thread
   - Searches X for relevant information
   - Logs analysis results
   - Generates content as needed

5. **Live Monitoring**: All decisions and actions are logged in real-time to the console

## 🔧 xMCP Server

The xMCP (X Model Context Protocol) server exposes X API functionality in a standardized way:

**Available Tools:**
- `x_fetch_mentions` - Get recent mentions
- `x_fetch_thread` - Get conversation threads
- `x_post_reply` - Post replies
- `x_search_tweets` - Search tweets

This allows Grok or other AI models to interact with X autonomously through a standard interface.

## 🎯 Example Scenarios

### Scenario 1: Question Reply
**User tweets:** "@yourusername Can you explain how blockchain works?"

**Agent action:**
1. Detects mention
2. Analyzes with Grok
3. Generates educational reply
4. Posts reply to thread

### Scenario 2: Research Request
**User tweets:** "@yourusername What's the latest on AI development?"

**Agent action:**
1. Detects mention
2. Searches X for recent AI news
3. Synthesizes findings
4. Replies with summary and sources

### Scenario 3: Thread Participation
**User mentions you in an ongoing discussion**

**Agent action:**
1. Fetches entire thread context
2. Understands conversation flow
3. Generates contextually relevant reply
4. Contributes meaningfully to discussion

## 🛡️ Safety & Best Practices

- **Rate Limiting**: The system respects X API rate limits
- **Context-Aware**: Analyzes full thread context before responding
- **Configurable Polling**: Adjust monitoring frequency to your needs
- **Error Handling**: Graceful degradation with simulation fallbacks
- **Privacy**: No data is stored; all processing is real-time

## 🤝 Contributing

Contributions are welcome! Areas for enhancement:
- Additional action types (like, retweet, quote tweet)
- Advanced Grok prompting strategies
- Webhook-based real-time monitoring
- Multi-account support
- Web dashboard for monitoring

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Built with [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)
- Powered by [Grok AI from xAI](https://x.ai/)
- X (Twitter) API integration

## 📧 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact: [Your contact info]

---

**⚡ Tag and watch your AI agent in action!** 🚀 
