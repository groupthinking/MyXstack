/**
 * Example: Custom Agent Usage
 * 
 * This example shows how to use MyXstack components programmatically
 * to build custom automation workflows.
 */

import { loadConfig } from './services/config.js';
import { XAPIClient } from './services/xapi.js';
import { GrokService } from './services/grok.js';

async function example1_fetchAndAnalyzeMention() {
  console.log('\n=== Example 1: Fetch and Analyze a Mention ===\n');
  
  const config = loadConfig();
  const xClient = new XAPIClient(config.xApiConfig);
  const grok = new GrokService(config.xaiApiKey);
  
  // Fetch recent mentions
  const mentions = await xClient.fetchMentions(config.username);
  console.log(`Found ${mentions.length} mention(s)`);
  
  if (mentions.length > 0) {
    const mention = mentions[0];
    console.log(`\nMention from @${mention.post.author_username}:`);
    console.log(`"${mention.post.text}"`);
    
    // Fetch thread context
    const conversationId = mention.post.conversation_id || mention.post.id;
    const thread = await xClient.fetchThread(conversationId);
    
    if (thread) {
      console.log(`\nThread has ${thread.replies.length + 1} posts`);
      
      // Analyze with Grok
      const analysis = await grok.analyzeAndDecide(mention.post.text, thread);
      
      console.log(`\nGrok's Decision:`);
      console.log(`  Action: ${analysis.action.type}`);
      console.log(`  Confidence: ${(analysis.confidence * 100).toFixed(1)}%`);
      console.log(`  Reasoning: ${analysis.explanation}`);
      
      if (analysis.action.content) {
        console.log(`  Suggested content: "${analysis.action.content}"`);
      }
    }
  }
}

async function example2_customReply() {
  console.log('\n=== Example 2: Post a Custom Reply ===\n');
  
  const config = loadConfig();
  const xClient = new XAPIClient(config.xApiConfig);
  
  // In this example, we manually specify a tweet to reply to
  const tweetId = 'sim_123456789'; // Replace with real tweet ID
  const replyText = 'Thanks for reaching out! This is an automated response from MyXstack. 🤖';
  
  console.log(`Posting reply to tweet ${tweetId}...`);
  const success = await xClient.postReply(tweetId, replyText);
  
  if (success) {
    console.log('✅ Reply posted successfully!');
  } else {
    console.log('❌ Failed to post reply');
  }
}

async function example3_searchAndSummarize() {
  console.log('\n=== Example 3: Search and Summarize ===\n');
  
  const config = loadConfig();
  const xClient = new XAPIClient(config.xApiConfig);
  const grok = new GrokService(config.xaiApiKey);
  
  // Search for tweets about a topic
  const query = 'artificial intelligence';
  console.log(`Searching for: "${query}"`);
  
  const results = await xClient.searchTweets(query);
  console.log(`Found ${results.length} results`);
  
  if (results.length > 0) {
    console.log('\nTop results:');
    results.slice(0, 3).forEach((tweet, idx) => {
      console.log(`${idx + 1}. @${tweet.author_username}: "${tweet.text}"`);
    });
    
    // You could then use Grok to summarize these results
    console.log('\n(In a real scenario, Grok could summarize these findings)');
  }
}

async function example4_monitorKeyword() {
  console.log('\n=== Example 4: Monitor Keyword ===\n');
  
  const config = loadConfig();
  const xClient = new XAPIClient(config.xApiConfig);
  
  const keyword = 'AI agent';
  console.log(`Monitoring keyword: "${keyword}"`);
  console.log('Checking every 10 seconds for 30 seconds...\n');
  
  let checks = 0;
  const maxChecks = 3;
  
  const intervalId = setInterval(async () => {
    checks++;
    console.log(`Check ${checks}/${maxChecks}...`);
    
    const results = await xClient.searchTweets(keyword);
    console.log(`  Found ${results.length} tweets mentioning "${keyword}"`);
    
    if (checks >= maxChecks) {
      clearInterval(intervalId);
      console.log('\n✅ Monitoring complete!');
    }
  }, 10000);
}

async function example5_batchProcessMentions() {
  console.log('\n=== Example 5: Batch Process Mentions ===\n');
  
  const config = loadConfig();
  const xClient = new XAPIClient(config.xApiConfig);
  const grok = new GrokService(config.xaiApiKey);
  
  // Fetch all mentions
  const mentions = await xClient.fetchMentions(config.username);
  console.log(`Processing ${mentions.length} mention(s) in batch...\n`);
  
  // Process each mention
  for (let i = 0; i < mentions.length; i++) {
    const mention = mentions[i];
    console.log(`[${i + 1}/${mentions.length}] Processing mention from @${mention.post.author_username}`);
    
    const conversationId = mention.post.conversation_id || mention.post.id;
    const thread = await xClient.fetchThread(conversationId);
    
    if (thread) {
      const analysis = await grok.analyzeAndDecide(mention.post.text, thread);
      console.log(`  → Action: ${analysis.action.type} (${(analysis.confidence * 100).toFixed(0)}% confidence)`);
      
      // In a real scenario, you might execute the action here
      // await executeAction(analysis.action);
    }
    
    console.log('');
  }
  
  console.log('✅ Batch processing complete!');
}

// Main function to run examples
async function main() {
  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║  MyXstack - Programmatic Usage Examples           ║');
  console.log('╚════════════════════════════════════════════════════╝');
  
  try {
    // Uncomment the example you want to run:
    
    await example1_fetchAndAnalyzeMention();
    // await example2_customReply();
    // await example3_searchAndSummarize();
    // await example4_monitorKeyword(); // This one runs for 30 seconds
    // await example5_batchProcessMentions();
    
    console.log('\n✨ Example completed successfully!\n');
  } catch (error) {
    console.error('❌ Error running example:', error);
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}

export {
  example1_fetchAndAnalyzeMention,
  example2_customReply,
  example3_searchAndSummarize,
  example4_monitorKeyword,
  example5_batchProcessMentions,
};
