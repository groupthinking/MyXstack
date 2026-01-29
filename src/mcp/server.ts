/**
 * xMCP Server - Model Context Protocol server for X (Twitter) API
 * Exposes X API tools in a standardized way for autonomous agent access
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { XAPIClient } from '../services/xapi.js';
import { XAPIConfig } from '../types/index.js';

export class XMCPServer {
  private server: Server;
  private xClient: XAPIClient;

  constructor(xApiConfig: XAPIConfig) {
    this.xClient = new XAPIClient(xApiConfig);
    this.server = new Server(
      {
        name: 'x-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
  }

  /**
   * Define available tools for the MCP server
   */
  private getTools(): Tool[] {
    return [
      {
        name: 'x_fetch_mentions',
        description: 'Fetch recent mentions of the authenticated user from X (Twitter)',
        inputSchema: {
          type: 'object',
          properties: {
            username: {
              type: 'string',
              description: 'The X username to fetch mentions for',
            },
          },
          required: ['username'],
        },
      },
      {
        name: 'x_fetch_thread',
        description: 'Fetch a complete thread/conversation from X (Twitter)',
        inputSchema: {
          type: 'object',
          properties: {
            conversation_id: {
              type: 'string',
              description: 'The conversation ID to fetch',
            },
          },
          required: ['conversation_id'],
        },
      },
      {
        name: 'x_post_reply',
        description: 'Post a reply to a tweet on X (Twitter)',
        inputSchema: {
          type: 'object',
          properties: {
            in_reply_to_tweet_id: {
              type: 'string',
              description: 'The tweet ID to reply to',
            },
            text: {
              type: 'string',
              description: 'The text content of the reply',
            },
          },
          required: ['in_reply_to_tweet_id', 'text'],
        },
      },
      {
        name: 'x_search_tweets',
        description: 'Search for tweets on X (Twitter)',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'The search query',
            },
          },
          required: ['query'],
        },
      },
    ];
  }

  /**
   * Setup handlers for MCP protocol requests
   */
  private setupToolHandlers(): void {
    // Handle tool listing
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: this.getTools(),
      };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      if (!args) {
        throw new Error('Missing arguments for tool call');
      }

      try {
        switch (name) {
          case 'x_fetch_mentions': {
            const mentions = await this.xClient.fetchMentions(args.username as string);
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(mentions, null, 2),
                },
              ],
            };
          }

          case 'x_fetch_thread': {
            const thread = await this.xClient.fetchThread(args.conversation_id as string);
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(thread, null, 2),
                },
              ],
            };
          }

          case 'x_post_reply': {
            const success = await this.xClient.postReply(
              args.in_reply_to_tweet_id as string,
              args.text as string
            );
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify({ success }, null, 2),
                },
              ],
            };
          }

          case 'x_search_tweets': {
            const results = await this.xClient.searchTweets(args.query as string);
            return {
              content: [
                {
                  type: 'text',
                  text: JSON.stringify(results, null, 2),
                },
              ],
            };
          }

          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({ error: errorMessage }, null, 2),
            },
          ],
          isError: true,
        };
      }
    });
  }

  /**
   * Start the MCP server
   */
  async start(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.log('🚀 xMCP Server started and listening for tool requests');
  }

  /**
   * Get the X API client (for direct access by the agent)
   */
  getXClient(): XAPIClient {
    return this.xClient;
  }
}
