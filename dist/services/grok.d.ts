/**
 * Grok AI Integration Service
 * Handles analysis and reasoning using Grok via xAI API
 */
import { XThread, GrokAnalysis } from '../types/index.js';
export declare class GrokService {
    private apiKey;
    private simulationMode;
    constructor(apiKey: string);
    /**
     * Analyze a mention and thread context to determine appropriate action
     */
    analyzeAndDecide(mention: string, thread: XThread): Promise<GrokAnalysis>;
    /**
     * Build the analysis prompt for Grok
     */
    private buildAnalysisPrompt;
    /**
     * Parse Grok's response into structured analysis
     */
    private parseGrokResponse;
    /**
     * Simulate Grok analysis for testing
     */
    private simulateAnalysis;
}
//# sourceMappingURL=grok.d.ts.map