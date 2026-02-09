/**
 * MyXstack - Autonomous AI Agent System on X (Twitter)
 * Main entry point
 */
import { loadConfig } from './services/config.js';
import { XAPIClient } from './services/xapi.js';
import { AutonomousAgent } from './services/agent.js';
import { XMCPServer } from './mcp/server.js';

async function main() {
  // Redirect console.log to stderr so it doesn't conflict with
  // MCP StdioServerTransport which uses stdout for protocol messages
  console.log = (...args: unknown[]) => console.error(...args);

  console.log('═══════════════════════════════════════════════════');
  console.log('  MyXstack - Autonomous AI Agent on X (Twitter)');
  console.log('═══════════════════════════════════════════════════\n');

  try {
    // Load configuration
    console.log('📋 Loading configuration...');
    const config = loadConfig();
    console.log('✅ Configuration loaded\n');

    // Initialize X API client
    console.log('🔧 Initializing X API client...');
    const xClient = new XAPIClient(config.xApiConfig);
    console.log('✅ X API client ready\n');

    // Initialize MCP server (runs in background)
    console.log('🌐 Initializing xMCP server...');
    const mcpServer = new XMCPServer(config.xApiConfig);
    console.log('✅ xMCP server ready\n');

    // Initialize and start autonomous agent
    console.log('🚀 Initializing autonomous agent...');
    const agent = new AutonomousAgent(config, xClient);
    
    // Setup graceful shutdown
    setupGracefulShutdown(agent);

    // Start the agent
    await agent.start();

    // Keep the process running
    await new Promise(() => {}); // Runs indefinitely until interrupted
  } catch (error) {
    console.error('❌ Fatal error:', error);
    process.exit(1);
  }
}

/**
 * Setup graceful shutdown handlers
 */
function setupGracefulShutdown(agent: AutonomousAgent) {
  const shutdown = () => {
    console.log('\n\n🔄 Received shutdown signal...');
    agent.stop();
    const stats = agent.getStats();
    console.log(`📊 Final stats: ${stats.processedMentions} mentions processed`);
    console.log('👋 Goodbye!\n');
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

// Run the application
main().catch((error) => {
  console.error('Unhandled error:', error);
  process.exit(1);
});
