/**
 * Autonomous Agent Orchestrator
 * Main coordinator that monitors mentions, analyzes with Grok, and executes actions
 */
import { XAPIClient } from '../services/xapi.js';
import { AgentConfig } from '../types/index.js';
export declare class AutonomousAgent {
    private xClient;
    private grokService;
    private config;
    private processedMentions;
    private isRunning;
    private pollingIntervalId;
    private isProcessing;
    constructor(config: AgentConfig, xClient: XAPIClient);
    /**
     * Start the autonomous agent
     */
    start(): Promise<void>;
    /**
     * Stop the autonomous agent
     */
    stop(): void;
    /**
     * Main processing loop: check for mentions and process them
     */
    private checkAndProcess;
    /**
     * Process a single mention
     */
    private processMention;
    /**
     * Execute an action determined by Grok
     */
    private executeAction;
    /**
     * Get agent statistics
     */
    getStats(): {
        processedMentions: number;
        isRunning: boolean;
    };
}
//# sourceMappingURL=agent.d.ts.map