/**
 * Configuration manager for the autonomous agent
 */
import dotenv from 'dotenv';
dotenv.config();
export function loadConfig() {
    const xApiConfig = {
        apiKey: process.env.X_API_KEY || '',
        apiSecret: process.env.X_API_SECRET || '',
        accessToken: process.env.X_ACCESS_TOKEN || '',
        accessTokenSecret: process.env.X_ACCESS_TOKEN_SECRET || '',
        bearerToken: process.env.X_BEARER_TOKEN || '',
    };
    const config = {
        username: process.env.X_USERNAME || '',
        xaiApiKey: process.env.XAI_API_KEY || '',
        xApiConfig,
        pollingIntervalMs: parseInt(process.env.POLLING_INTERVAL_MS || '30000'),
        maxRetries: parseInt(process.env.MAX_RETRIES || '3'),
    };
    // Validate required fields
    if (!config.username) {
        throw new Error('X_USERNAME is required in environment variables');
    }
    if (!config.xApiConfig.bearerToken) {
        console.warn('X_BEARER_TOKEN not set - X API calls will be simulated');
    }
    if (!config.xaiApiKey) {
        console.warn('XAI_API_KEY not set - Grok AI calls will be simulated');
    }
    return config;
}
//# sourceMappingURL=config.js.map