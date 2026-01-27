/**
 * X (Twitter) API Client Service
 * Handles all interactions with the X API for fetching mentions, posts, and posting replies
 */
import { XPost, XThread, Mention, XAPIConfig } from '../types/index.js';
export declare class XAPIClient {
    private config;
    private lastMentionId;
    private simulationMode;
    constructor(config: XAPIConfig);
    /**
     * Fetch recent mentions of the authenticated user
     */
    fetchMentions(username: string): Promise<Mention[]>;
    /**
     * Fetch a complete thread/conversation
     */
    fetchThread(conversationId: string): Promise<XThread | null>;
    /**
     * Post a reply to a tweet
     */
    postReply(inReplyToTweetId: string, text: string): Promise<boolean>;
    /**
     * Search for tweets
     */
    searchTweets(query: string): Promise<XPost[]>;
    private makeXAPIRequest;
    private parseMentions;
    private parsePost;
    private parseThread;
    private simulateFetchMentions;
    private simulateFetchThread;
    private simulatePostReply;
    private simulateSearchTweets;
}
//# sourceMappingURL=xapi.d.ts.map