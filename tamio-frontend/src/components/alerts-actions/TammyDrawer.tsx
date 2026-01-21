/**
 * TammyDrawer Component - V4 Risk/Controls Architecture
 *
 * Slide-in drawer for Tammy chat integration.
 * Features:
 * - Slide in from right (~420px wide)
 * - Risk context banner when preloaded
 * - Streaming chat messages
 * - Session persistence
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  X,
  Send,
  AlertCircle,
  Loader2,
  Bot,
  User,
  Sparkles,
} from 'lucide-react';
import { sendChatMessageStreaming, type StreamEvent } from '@/lib/api/tami';
import type { Risk } from '@/lib/api/alertsActions';
import { formatRiskForTammy } from '@/contexts/AlertsActionsContext';
import { useAuth } from '@/contexts/AuthContext';
import { StructuredResponse } from '@/components/chat/StructuredResponse';

interface TammyDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  preloadedRisk: Risk | null;
  sessionId: string | null;
  onSessionCreate: (sessionId: string) => void;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export function TammyDrawer({
  isOpen,
  onClose,
  preloadedRisk,
  sessionId: _sessionId, // Reserved for future session persistence
  onSessionCreate,
}: TammyDrawerProps) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [hasAutoSent, setHasAutoSent] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-send context when drawer opens with a preloaded risk
  useEffect(() => {
    if (isOpen && preloadedRisk && !hasAutoSent && user) {
      setHasAutoSent(true);
      const contextMessage = formatRiskForTammy(preloadedRisk);
      handleSend(contextMessage);
    }
  }, [isOpen, preloadedRisk, hasAutoSent, user]);

  // Reset hasAutoSent when drawer closes
  useEffect(() => {
    if (!isOpen) {
      setHasAutoSent(false);
    }
  }, [isOpen]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when drawer opens
  useEffect(() => {
    if (isOpen && !preloadedRisk) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen, preloadedRisk]);

  const handleSend = useCallback(
    async (messageContent?: string) => {
      const content = messageContent || input.trim();
      if (!content || !user) return;

      const userMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setInput('');
      setIsLoading(true);

      // Create assistant message placeholder for streaming
      const assistantMessageId = `msg-${Date.now() + 1}`;
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      try {
        await sendChatMessageStreaming(
          {
            user_id: user.id,
            message: content,
            conversation_history: messages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            active_scenario_id: null,
          },
          // On chunk
          (chunk) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: m.content + chunk }
                  : m
              )
            );
          },
          // On done
          (event: StreamEvent) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId ? { ...m, isStreaming: false } : m
              )
            );
            setIsLoading(false);

            // Update session ID if returned
            if (event.context_summary?.session_id) {
              onSessionCreate(event.context_summary.session_id as string);
            }
          },
          // On error
          (error) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      content: `Sorry, I encountered an error: ${error}`,
                      isStreaming: false,
                    }
                  : m
              )
            );
            setIsLoading(false);
          }
        );
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId
              ? {
                  ...m,
                  content: 'Sorry, I encountered an unexpected error. Please try again.',
                  isStreaming: false,
                }
              : m
          )
        );
        setIsLoading(false);
      }
    },
    [input, user, messages, onSessionCreate]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          'fixed inset-0 bg-black/20 transition-opacity z-40',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          'fixed right-0 top-0 h-full w-[420px] bg-white shadow-2xl z-50',
          'flex flex-col',
          'transform transition-transform duration-300 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-lime/10 flex items-center justify-center">
              <Bot className="w-4 h-4 text-lime-600" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-gunmetal">Tammy</h2>
              <p className="text-xs text-gray-500">Cash flow advisor</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Risk Context Banner */}
        {preloadedRisk && (
          <div className="px-4 py-3 bg-gradient-to-r from-tomato/5 to-amber-500/5 border-b border-gray-100">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-tomato flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-medium text-gunmetal">
                  Reviewing risk:
                </p>
                <p className="text-xs text-gray-600 line-clamp-2">
                  {preloadedRisk.title}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && !preloadedRisk && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-12 h-12 rounded-full bg-lime/10 flex items-center justify-center mb-3">
                <Sparkles className="w-6 h-6 text-lime-600" />
              </div>
              <h3 className="text-sm font-semibold text-gunmetal mb-1">
                How can I help?
              </h3>
              <p className="text-xs text-gray-500 max-w-[280px]">
                Ask me about your cash flow risks, controls, or how to protect
                your buffer.
              </p>

              {/* Example prompts */}
              <div className="mt-4 space-y-2">
                {[
                  'What risks should I focus on first?',
                  'How can I improve my cash position?',
                  'Explain my current controls',
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setInput(prompt)}
                    className="block w-full px-3 py-2 text-xs text-left text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex gap-2',
                message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
              )}
            >
              <div
                className={cn(
                  'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0',
                  message.role === 'user'
                    ? 'bg-gunmetal'
                    : 'bg-lime/10'
                )}
              >
                {message.role === 'user' ? (
                  <User className="w-3.5 h-3.5 text-white" />
                ) : (
                  <Bot className="w-3.5 h-3.5 text-lime-600" />
                )}
              </div>

              <div
                className={cn(
                  'max-w-[85%] rounded-xl px-3 py-2',
                  message.role === 'user'
                    ? 'bg-gunmetal text-white'
                    : 'bg-gray-50'
                )}
              >
                {message.role === 'assistant' ? (
                  <StructuredResponse content={message.content} />
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                )}

                {message.isStreaming && (
                  <span className="inline-block w-1.5 h-4 bg-lime-600 animate-pulse ml-0.5" />
                )}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-4 py-3 border-t border-gray-200">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Tammy..."
              disabled={isLoading}
              rows={1}
              className={cn(
                'flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2',
                'text-sm placeholder:text-gray-400',
                'focus:outline-none focus:ring-2 focus:ring-lime/50 focus:border-lime',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'max-h-32'
              )}
              style={{ minHeight: '40px' }}
            />
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className="h-10 w-10 p-0 bg-lime hover:bg-lime/90 text-gunmetal rounded-xl"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
