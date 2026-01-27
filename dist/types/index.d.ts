/**
 * Type definitions for the autonomous X agent system
 */
export interface XPost {
    id: string;
    text: string;
    author_id: string;
    author_username: string;
    created_at: string;
    conversation_id?: string;
    in_reply_to_user_id?: string;
    referenced_tweets?: Array<{
        type: string;
        id: string;
    }>;
}
export interface XThread {
    root_post: XPost;
    replies: XPost[];
}
export interface Mention {
    post: XPost;
    mentioned_at: Date;
    processed: boolean;
}
export interface AgentAction {
    type: 'reply' | 'search' | 'generate' | 'analyze';
    target_post_id: string;
    content?: string;
    query?: string;
    reasoning?: string;
}
export interface GrokAnalysis {
    action: AgentAction;
    confidence: number;
    explanation: string;
}
export interface XAPIConfig {
    apiKey: string;
    apiSecret: string;
    accessToken: string;
    accessTokenSecret: string;
    bearerToken: string;
}
export interface AgentConfig {
    username: string;
    xaiApiKey: string;
    xApiConfig: XAPIConfig;
    pollingIntervalMs: number;
    maxRetries: number;
}
//# sourceMappingURL=index.d.ts.map