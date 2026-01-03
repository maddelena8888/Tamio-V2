// ============================================================================
// TAMI Chat API - Following exact contract from specification
// ============================================================================

import api, { getAccessToken } from './client';
import type { ChatRequest, ChatResponse, ChatMessage, ChatMode, UIHints } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Stream event types from the server
 */
export interface StreamEvent {
  type: 'chunk' | 'done' | 'error';
  content?: string;
  mode?: ChatMode;
  ui_hints?: UIHints;
  context_summary?: Record<string, unknown>;
  error?: string;
}

/**
 * Send a message to TAMI chat with streaming response
 *
 * This provides much lower perceived latency as the user sees
 * the response appear character by character.
 */
export async function sendChatMessageStreaming(
  request: ChatRequest,
  onChunk: (content: string) => void,
  onDone: (event: StreamEvent) => void,
  onError: (error: string) => void
): Promise<void> {
  const token = getAccessToken();

  const response = await fetch(`${API_BASE_URL}/tami/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    onError(error.detail || 'Failed to connect to TAMI');
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError('No response body');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE messages
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const event: StreamEvent = JSON.parse(line.slice(6));

          if (event.type === 'chunk' && event.content) {
            onChunk(event.content);
          } else if (event.type === 'done') {
            onDone(event);
          } else if (event.type === 'error') {
            onError(event.error || 'Unknown error');
          }
        } catch {
          // Ignore parse errors for incomplete messages
        }
      }
    }
  }
}

/**
 * Send a message to TAMI chat (non-streaming)
 *
 * IMPORTANT: Follow the contract exactly:
 * - Response contains message_markdown, mode, and ui_hints
 * - mode determines UI behavior (explain_forecast, suggest_scenarios, build_scenario, goal_planning, clarify)
 * - ui_hints.suggested_actions are rendered as buttons
 * - Frontend never applies scenarios directly - all changes flow through TAMI
 */
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  return api.post<ChatResponse>('/tami/chat', request);
}

/**
 * Create or update a scenario layer via TAMI
 */
export async function createOrUpdateScenarioLayer(params: {
  user_id: string;
  scenario_type: string;
  scope: Record<string, unknown>;
  params: Record<string, unknown>;
  linked_changes?: Record<string, unknown> | null;
  name: string;
}): Promise<unknown> {
  return api.post('/tami/scenario/layer/create_or_update', params);
}

/**
 * Iterate on an existing scenario layer
 */
export async function iterateScenarioLayer(params: {
  scenario_id: string;
  patch: Record<string, unknown>;
}): Promise<unknown> {
  return api.post('/tami/scenario/layer/iterate', params);
}

/**
 * Discard a scenario layer
 */
export async function discardScenarioLayer(params: {
  scenario_id: string;
}): Promise<unknown> {
  return api.post('/tami/scenario/layer/discard', params);
}

/**
 * Get scenario suggestions
 */
export async function getScenarioSuggestions(userId: string): Promise<unknown> {
  return api.get('/tami/scenario/suggestions', { user_id: userId });
}

/**
 * Build scenarios to achieve a financial goal
 */
export async function planGoal(params: {
  user_id: string;
  goal: string;
  constraints: Record<string, unknown>;
}): Promise<unknown> {
  return api.post('/tami/plan/goal', params);
}

/**
 * Get TAMI context (debugging)
 */
export async function getTamiContext(userId: string): Promise<unknown> {
  return api.get('/tami/context', { user_id: userId });
}

// Helper function to format conversation history
export function formatConversationHistory(
  messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp?: Date }>
): ChatMessage[] {
  return messages.map((msg) => ({
    role: msg.role,
    content: msg.content,
    timestamp: msg.timestamp?.toISOString(),
  }));
}
