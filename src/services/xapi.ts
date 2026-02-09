/**
 * X (Twitter) API Client Service
 * Handles all interactions with the X API for fetching mentions, posts, and posting replies
 */
import { XPost, XThread, Mention, XAPIConfig } from '../types/index.js';

export class XAPIClient {
  private config: XAPIConfig;
  private lastMentionId: string | null = null;
  private simulationMode: boolean = false;
  private static readonly MAX_MENTIONS_PER_FETCH = 10;

  constructor(config: XAPIConfig) {
    this.config = config;
    this.simulationMode = !config.bearerToken;
    
    if (this.simulationMode) {
      console.log('⚠️  Running in simulation mode - X API calls will be mocked');
    }
  }

  /**
   * Fetch recent mentions of the authenticated user
   */
  async fetchMentions(username: string): Promise<Mention[]> {
    if (this.simulationMode) {
      return this.simulateFetchMentions(username);
    }

    try {
      // In a real implementation, this would call X API v2
      // GET /2/users/:id/mentions
      const response = await this.makeXAPIRequest(
        `https://api.twitter.com/2/users/by/username/${username}`,
        'GET'
      );
      
      if (!response || !response.data) {
        console.warn('Invalid response from X API (user lookup)');
        return [];
      }

      const userId = response.data.id;
      if (!userId) {
        throw new Error('Failed to get user ID from response');
      }

      const params = new URLSearchParams({
        max_results: String(XAPIClient.MAX_MENTIONS_PER_FETCH),
        expansions: 'author_id',
        'tweet.fields': 'created_at,conversation_id,in_reply_to_user_id,referenced_tweets',
      });
      if (this.lastMentionId) {
        params.set('since_id', this.lastMentionId);
      }
      const mentionsUrl = `https://api.twitter.com/2/users/${userId}/mentions?${params.toString()}`;

      const mentionsResponse = await this.makeXAPIRequest(mentionsUrl, 'GET');

      if (!mentionsResponse || !Array.isArray(mentionsResponse.data)) {
        console.warn('Invalid response from X API (mentions)');
        return [];
      }

      const mentions = this.parseMentions(mentionsResponse.data);

      // Track the newest mention ID for pagination on the next poll
      if (mentionsResponse.data.length > 0 && mentionsResponse.data[0]?.id) {
        this.lastMentionId = mentionsResponse.data[0].id;
      }

      return mentions;
    } catch (error) {
      console.error('Error fetching mentions:', error);
      return [];
    }
  }

  /**
   * Fetch a complete thread/conversation
   */
  async fetchThread(conversationId: string): Promise<XThread | null> {
    if (this.simulationMode) {
      return this.simulateFetchThread(conversationId);
    }

    try {
      // In a real implementation, this would use X API v2 search
      // to get all tweets in a conversation
      const response = await this.makeXAPIRequest(
        `https://api.twitter.com/2/tweets/search/recent?query=conversation_id:${conversationId}&max_results=100&tweet.fields=created_at,author_id,conversation_id,referenced_tweets`,
        'GET'
      );

      if (!response || !Array.isArray(response.data)) {
        console.warn('Unexpected response shape from X API (thread): data is not an array');
        return null;
      }

      return this.parseThread(response.data);
    } catch (error) {
      console.error('Error fetching thread:', error);
      return null;
    }
  }

  /**
   * Post a reply to a tweet
   */
  async postReply(inReplyToTweetId: string, text: string): Promise<boolean> {
    if (this.simulationMode) {
      return this.simulatePostReply(inReplyToTweetId, text);
    }

    try {
      // In a real implementation, this would call X API v2
      // POST /2/tweets
      const response = await this.makeXAPIRequest(
        'https://api.twitter.com/2/tweets',
        'POST',
        {
          text,
          reply: {
            in_reply_to_tweet_id: inReplyToTweetId,
          },
        }
      );

      return !!response.data?.id;
    } catch (error) {
      console.error('Error posting reply:', error);
      return false;
    }
  }

  /**
   * Search for tweets
   */
  async searchTweets(query: string): Promise<XPost[]> {
    if (this.simulationMode) {
      return this.simulateSearchTweets(query);
    }

    try {
      const response = await this.makeXAPIRequest(
        `https://api.twitter.com/2/tweets/search/recent?query=${encodeURIComponent(query)}&max_results=10&tweet.fields=created_at,author_id,conversation_id`,
        'GET'
      );

      return (response.data || []).map((tweet: any) => this.parsePost(tweet));
    } catch (error) {
      console.error('Error searching tweets:', error);
      return [];
    }
  }

  // Private helper methods

  private async makeXAPIRequest(url: string, method: string, body?: any): Promise<any> {
    const headers: Record<string, string> = {
      'Authorization': `Bearer ${this.config.bearerToken}`,
      'Content-Type': 'application/json',
    };

    const options: RequestInit = {
      method,
      headers,
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    
    if (!response.ok) {
      throw new Error(`X API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  private parseMentions(tweets: any[]): Mention[] {
    return tweets.map((tweet) => ({
      post: this.parsePost(tweet),
      mentioned_at: new Date(tweet.created_at),
      processed: false,
    }));
  }

  private parsePost(tweet: any): XPost {
    return {
      id: tweet.id,
      text: tweet.text,
      author_id: tweet.author_id,
      author_username: tweet.username || 'unknown',
      created_at: tweet.created_at,
      conversation_id: tweet.conversation_id,
      in_reply_to_user_id: tweet.in_reply_to_user_id,
      referenced_tweets: tweet.referenced_tweets,
    };
  }

  private parseThread(tweets: { created_at: string; [key: string]: unknown }[]): XThread | null {
    if (tweets.length === 0) return null;

    const sorted = [...tweets].sort((a, b) => 
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

    return {
      root_post: this.parsePost(sorted[0]),
      replies: sorted.slice(1).map((t) => this.parsePost(t)),
    };
  }

  // Simulation methods for testing without real API credentials

  private simulateFetchMentions(username: string): Mention[] {
    const simulatedMentions: Mention[] = [
      {
        post: {
          id: 'sim_123456789',
          text: `@${username} Can you analyze this market trend and give me insights?`,
          author_id: 'sim_user_001',
          author_username: 'test_user',
          created_at: new Date().toISOString(),
          conversation_id: 'sim_conv_001',
        },
        mentioned_at: new Date(),
        processed: false,
      },
    ];

    console.log(`📨 Simulated: Found ${simulatedMentions.length} mention(s)`);
    return simulatedMentions;
  }

  private simulateFetchThread(conversationId: string): XThread {
    const thread: XThread = {
      root_post: {
        id: 'sim_root_123',
        text: 'This is the root post of the conversation',
        author_id: 'sim_user_001',
        author_username: 'test_user',
        created_at: new Date(Date.now() - 60000).toISOString(),
        conversation_id: conversationId,
      },
      replies: [
        {
          id: 'sim_reply_456',
          text: 'This is a reply in the thread',
          author_id: 'sim_user_002',
          author_username: 'another_user',
          created_at: new Date().toISOString(),
          conversation_id: conversationId,
        },
      ],
    };

    console.log(`🧵 Simulated: Fetched thread with ${thread.replies.length + 1} posts`);
    return thread;
  }

  private simulatePostReply(inReplyToTweetId: string, text: string): boolean {
    console.log(`📤 Simulated: Would post reply to ${inReplyToTweetId}:`);
    console.log(`   "${text}"`);
    return true;
  }

  private simulateSearchTweets(query: string): XPost[] {
    console.log(`🔍 Simulated: Searched for "${query}"`);
    return [
      {
        id: 'sim_search_001',
        text: `Sample tweet matching query: ${query}`,
        author_id: 'sim_user_003',
        author_username: 'search_result_user',
        created_at: new Date().toISOString(),
      },
    ];
  }
}
