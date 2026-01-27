import { GrokService } from '../services/grok.js';
export class AutonomousAgent {
    xClient;
    grokService;
    config;
    processedMentions = new Set();
    isRunning = false;
    pollingIntervalId = null;
    isProcessing = false;
    constructor(config, xClient) {
        this.config = config;
        this.xClient = xClient;
        this.grokService = new GrokService(config.xaiApiKey);
    }
    /**
     * Start the autonomous agent
     */
    async start() {
        console.log('🤖 Starting Autonomous Agent...');
        console.log(`👤 Monitoring account: @${this.config.username}`);
        console.log(`⏱️  Polling interval: ${this.config.pollingIntervalMs}ms`);
        console.log('');
        this.isRunning = true;
        // Initial check
        await this.checkAndProcess();
        // Set up polling interval
        this.pollingIntervalId = setInterval(async () => {
            if (this.isRunning) {
                await this.checkAndProcess();
            }
            else {
                if (this.pollingIntervalId) {
                    clearInterval(this.pollingIntervalId);
                    this.pollingIntervalId = null;
                }
            }
        }, this.config.pollingIntervalMs);
        console.log('✅ Agent is now running. Monitoring for mentions...\n');
    }
    /**
     * Stop the autonomous agent
     */
    stop() {
        console.log('\n🛑 Stopping agent...');
        this.isRunning = false;
        if (this.pollingIntervalId) {
            clearInterval(this.pollingIntervalId);
            this.pollingIntervalId = null;
        }
    }
    /**
     * Main processing loop: check for mentions and process them
     */
    async checkAndProcess() {
        // Prevent concurrent processing
        if (this.isProcessing) {
            console.log(`⏳ [${new Date().toLocaleTimeString()}] Previous processing still in progress, skipping...`);
            return;
        }
        this.isProcessing = true;
        try {
            // Fetch new mentions
            const mentions = await this.xClient.fetchMentions(this.config.username);
            // Filter out already processed mentions
            const newMentions = mentions.filter((m) => !this.processedMentions.has(m.post.id));
            if (newMentions.length === 0) {
                console.log(`⏳ [${new Date().toLocaleTimeString()}] No new mentions`);
                return;
            }
            console.log(`\n📬 [${new Date().toLocaleTimeString()}] Found ${newMentions.length} new mention(s)!\n`);
            // Process each mention
            for (const mention of newMentions) {
                await this.processMention(mention);
                this.processedMentions.add(mention.post.id);
            }
        }
        catch (error) {
            console.error('❌ Error in processing loop:', error);
        }
        finally {
            this.isProcessing = false;
        }
    }
    /**
     * Process a single mention
     */
    async processMention(mention) {
        console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        console.log('📝 Processing Mention:');
        console.log(`   From: @${mention.post.author_username}`);
        console.log(`   Text: "${mention.post.text}"`);
        console.log(`   ID: ${mention.post.id}`);
        try {
            // Fetch thread context
            const conversationId = mention.post.conversation_id || mention.post.id;
            console.log('\n🧵 Fetching thread context...');
            const thread = await this.xClient.fetchThread(conversationId);
            if (!thread) {
                console.log('⚠️  Could not fetch thread context');
                return;
            }
            console.log(`   Thread has ${thread.replies.length + 1} posts`);
            // Analyze with Grok
            console.log('\n🤖 Analyzing with Grok AI...');
            const analysis = await this.grokService.analyzeAndDecide(mention.post.text, thread);
            console.log(`   Action: ${analysis.action.type.toUpperCase()}`);
            console.log(`   Confidence: ${(analysis.confidence * 100).toFixed(1)}%`);
            console.log(`   Reasoning: ${analysis.explanation}`);
            // Execute the action
            console.log('\n⚡ Executing action...');
            await this.executeAction(analysis.action);
            console.log('✅ Mention processed successfully!\n');
        }
        catch (error) {
            console.error('❌ Error processing mention:', error);
        }
    }
    /**
     * Execute an action determined by Grok
     */
    async executeAction(action) {
        switch (action.type) {
            case 'reply':
                if (action.content) {
                    const success = await this.xClient.postReply(action.target_post_id, action.content);
                    if (success) {
                        console.log('   ✓ Reply posted successfully');
                        console.log(`   📝 "${action.content}"`);
                    }
                    else {
                        console.log('   ✗ Failed to post reply');
                    }
                }
                break;
            case 'search':
                if (action.query) {
                    const results = await this.xClient.searchTweets(action.query);
                    console.log(`   ✓ Search completed: found ${results.length} results`);
                    console.log(`   🔍 Query: "${action.query}"`);
                }
                break;
            case 'analyze':
                console.log('   ✓ Analysis complete (no action taken)');
                if (action.reasoning) {
                    console.log(`   💡 ${action.reasoning}`);
                }
                break;
            case 'generate':
                console.log('   ✓ Content generated');
                if (action.content) {
                    console.log(`   📄 "${action.content}"`);
                }
                break;
            default:
                console.log(`   ⚠️  Unknown action type: ${action.type}`);
        }
    }
    /**
     * Get agent statistics
     */
    getStats() {
        return {
            processedMentions: this.processedMentions.size,
            isRunning: this.isRunning,
        };
    }
}
//# sourceMappingURL=agent.js.map