/**
 * Grok AI Integration Service
 * Handles analysis and reasoning using Grok via xAI API
 */
import { XThread, GrokAnalysis, AgentAction } from '../types/index.js';

export class GrokService {
  private apiKey: string;
  private simulationMode: boolean = false;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
    this.simulationMode = !apiKey;

    if (this.simulationMode) {
      console.log('⚠️  Running in simulation mode - Grok AI calls will be mocked');
    }
  }

  /**
   * Analyze a mention and thread context to determine appropriate action
   * @param mention - The text content of the mention to analyze
   * @param thread - The thread context including root post and replies
   * @param mentionPostId - The ID of the post where the agent was mentioned
   * @returns Analysis with recommended action
   */
  async analyzeAndDecide(mention: string, thread: XThread, mentionPostId: string): Promise<GrokAnalysis> {
    if (this.simulationMode) {
      return this.simulateAnalysis(mention, thread, mentionPostId);
    }

    try {
      const prompt = this.buildAnalysisPrompt(mention, thread);
      
      // Call xAI Grok API
      const response = await fetch('https://api.x.ai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          model: 'grok-beta',
          messages: [
            {
              role: 'system',
              content: 'You are an autonomous AI agent for X (Twitter). Analyze mentions and decide on appropriate actions: reply, search, or analyze. Respond in JSON format with action type, content, and reasoning.',
            },
            {
              role: 'user',
              content: prompt,
            },
          ],
          temperature: 0.7,
        }),
      });

      if (!response.ok) {
        throw new Error(`Grok API error: ${response.status}`);
      }

      const data = await response.json() as { choices: { message?: { content?: string } }[] };
      const analysisText = data.choices[0]?.message?.content || '';
      
      // Use the mention post ID so replies target the specific post where the agent was mentioned
      return this.parseGrokResponse(analysisText, mentionPostId);
    } catch (error) {
      console.error('Error calling Grok API:', error);
      // Fallback to simulation
      return this.simulateAnalysis(mention, thread, mentionPostId);
    }
  }

  /**
   * Build the analysis prompt for Grok
   */
  private buildAnalysisPrompt(mention: string, thread: XThread): string {
    let prompt = `I've been mentioned in a tweet. Here's the context:\n\n`;
    prompt += `MENTION: "${mention}"\n\n`;
    
    if (thread.replies.length > 0) {
      prompt += `THREAD CONTEXT:\n`;
      prompt += `Root: "${thread.root_post.text}"\n`;
      thread.replies.forEach((reply, idx) => {
        prompt += `Reply ${idx + 1}: "${reply.text}"\n`;
      });
      prompt += `\n`;
    }

    prompt += `Based on this mention, decide what action I should take. Options:\n`;
    prompt += `1. REPLY - Craft a thoughtful reply to engage with the user\n`;
    prompt += `2. SEARCH - Search for additional context or information\n`;
    prompt += `3. ANALYZE - Provide analysis without replying\n\n`;
    prompt += `Respond in this JSON format:\n`;
    prompt += `{\n`;
    prompt += `  "action": "reply|search|analyze",\n`;
    prompt += `  "content": "your reply text or search query",\n`;
    prompt += `  "confidence": 0.0-1.0,\n`;
    prompt += `  "reasoning": "why you chose this action"\n`;
    prompt += `}`;

    return prompt;
  }

  /**
   * Parse Grok's response into structured analysis
   */
  private parseGrokResponse(response: string, mentionPostId: string): GrokAnalysis {
    try {
      // Try to extract JSON from the response
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('No JSON found in response');
      }

      const parsed = JSON.parse(jsonMatch[0]);
      
      const action: AgentAction = {
        type: parsed.action as any,
        target_post_id: mentionPostId,
        content: parsed.content,
        query: parsed.action === 'search' ? parsed.content : undefined,
        reasoning: parsed.reasoning,
      };

      return {
        action,
        confidence: parsed.confidence || 0.8,
        explanation: parsed.reasoning || 'No explanation provided',
      };
    } catch (error) {
      console.error('Error parsing Grok response:', error);
      // Fallback to analysis-only action (no content posted)
      return {
        action: {
          type: 'analyze',
          target_post_id: mentionPostId,
          reasoning: 'Unable to parse AI response - defaulting to analyze-only mode',
        },
        confidence: 0.3,
        explanation: 'Used fallback due to response parsing error - no action taken',
      };
    }
  }

  /**
   * Simulate Grok analysis for testing
   */
  private simulateAnalysis(mention: string, thread: XThread, mentionPostId: string): GrokAnalysis {
    console.log('🤖 Simulated Grok Analysis:');
    console.log(`   Analyzing: "${mention}"`);
    
    // Simple heuristic: if mention contains question words, reply
    const questionWords = ['what', 'how', 'why', 'when', 'where', 'can you', 'could you'];
    const isQuestion = questionWords.some(word => 
      mention.toLowerCase().includes(word)
    );

    if (isQuestion) {
      const analysis: GrokAnalysis = {
        action: {
          type: 'reply',
          target_post_id: mentionPostId,
          content: 'Thanks for reaching out! I\'ve analyzed your question and here\'s my insight: Based on the context, I\'d recommend exploring this topic further. Let me know if you need more specific information!',
          reasoning: 'Detected a question, providing helpful response',
        },
        confidence: 0.85,
        explanation: 'User asked a question, best action is to provide a helpful reply',
      };
      
      console.log(`   Decision: REPLY (confidence: ${analysis.confidence})`);
      console.log(`   Reasoning: ${analysis.explanation}`);
      return analysis;
    } else {
      const analysis: GrokAnalysis = {
        action: {
          type: 'analyze',
          target_post_id: mentionPostId,
          reasoning: 'No clear action needed, just acknowledgment',
        },
        confidence: 0.7,
        explanation: 'Mention doesn\'t require immediate action',
      };
      
      console.log(`   Decision: ANALYZE (confidence: ${analysis.confidence})`);
      return analysis;
    }
  }
}
