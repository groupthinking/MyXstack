import { XAPIClient } from '../services/xapi.js';
import { XAPIConfig } from '../types/index.js';
export declare class XMCPServer {
    private server;
    private xClient;
    constructor(xApiConfig: XAPIConfig);
    /**
     * Define available tools for the MCP server
     */
    private getTools;
    /**
     * Setup handlers for MCP protocol requests
     */
    private setupToolHandlers;
    /**
     * Start the MCP server
     */
    start(): Promise<void>;
    /**
     * Get the X API client (for direct access by the agent)
     */
    getXClient(): XAPIClient;
}
//# sourceMappingURL=server.d.ts.map