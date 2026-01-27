/**
 * GlobalTAMIDrawer - Global AI Chatbot Drawer
 *
 * Slide-in drawer for the global TAMI chatbot.
 * Features:
 * - Slide in from right (~420px wide)
 * - Page context banner showing current page info
 * - Streaming chat messages
 * - Dynamic suggested prompts based on page
 * - Session persistence
 */

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  X,
  Send,
  Bot,
  User,
  Sparkles,
  Loader2,
  MapPin,
  Trash2,
} from 'lucide-react';
import { useTAMI, getSuggestedPrompts } from '@/contexts/TAMIContext';
import { StructuredResponse } from '@/components/chat/StructuredResponse';

// ============================================================================
// Page Context Banner
// ============================================================================

function PageContextBanner() {
  const { pageContext } = useTAMI();

  if (!pageContext || !pageContext.pageData) {
    return null;
  }

  const { page, pageData } = pageContext;

  // Generate context description based on page
  let contextDescription = '';
  switch (page) {
    case 'alerts-home':
    case 'home':
      if (pageData.currentAlert) {
        contextDescription = `Viewing: ${pageData.currentAlert.title}`;
      } else {
        contextDescription = 'Alerts dashboard';
      }
      break;
    case 'forecast':
      contextDescription = pageData.activeScenario
        ? `Forecast with "${pageData.activeScenario.name}" scenario`
        : `${pageData.timeRange || '13-week'} forecast`;
      break;
    case 'alert-impact':
      if (pageData.currentAlert) {
        contextDescription = `Analyzing: ${pageData.currentAlert.title}`;
      }
      break;
    case 'scenario-builder':
    case 'scenarios':
      contextDescription = pageData.builderMode
        ? `Building ${pageData.scenarioType || 'scenario'} (${pageData.builderMode})`
        : 'Scenario builder';
      break;
    default:
      contextDescription = `On ${page} page`;
  }

  if (!contextDescription) return null;

  return (
    <div className="px-4 py-2 bg-gradient-to-r from-lime/5 to-lime/10 border-b border-gray-100">
      <div className="flex items-center gap-2">
        <MapPin className="w-3.5 h-3.5 text-lime-600 flex-shrink-0" />
        <p className="text-xs text-gray-600 truncate">{contextDescription}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Empty State
// ============================================================================

function EmptyState({ onPromptSelect }: { onPromptSelect: (prompt: string) => void }) {
  const { pageContext } = useTAMI();
  const prompts = getSuggestedPrompts(pageContext?.page || 'default');

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-4">
      <div className="w-12 h-12 rounded-full bg-lime/10 flex items-center justify-center mb-3">
        <Sparkles className="w-6 h-6 text-lime-600" />
      </div>
      <h3 className="text-sm font-semibold text-gunmetal mb-1">
        How can I help?
      </h3>
      <p className="text-xs text-gray-500 max-w-[280px]">
        Ask me about your cash flow, risks, scenarios, or anything about your finances.
      </p>

      {/* Suggested prompts */}
      <div className="mt-4 space-y-2 w-full max-w-[300px]">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onPromptSelect(prompt)}
            className="block w-full px-3 py-2 text-xs text-left text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function GlobalTAMIDrawer() {
  const {
    isOpen,
    close,
    messages,
    isLoading,
    sendMessage,
    clearConversation,
    pageContext,
  } = useTAMI();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when drawer opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const message = input.trim();
    setInput('');
    await sendMessage(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePromptSelect = (prompt: string) => {
    setInput(prompt);
    inputRef.current?.focus();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          'fixed inset-0 bg-black/20 transition-opacity z-40',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={close}
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
              <h2 className="text-sm font-semibold text-gunmetal">TAMI</h2>
              <p className="text-xs text-gray-500">Your AI assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearConversation}
                className="h-8 w-8 p-0 text-gray-400 hover:text-gray-600"
                title="Clear conversation"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={close}
              className="h-8 w-8 p-0"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Page Context Banner */}
        <PageContextBanner />

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 ? (
            <EmptyState onPromptSelect={handlePromptSelect} />
          ) : (
            <>
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
                      message.role === 'user' ? 'bg-gunmetal' : 'bg-lime/10'
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

              {/* Quick prompts after messages */}
              {!isLoading && messages.length > 0 && (
                <div className="pt-2">
                  <p className="text-xs text-gray-400 mb-2">Suggested follow-ups:</p>
                  <div className="flex flex-wrap gap-2">
                    {getSuggestedPrompts(pageContext?.page || 'default')
                      .slice(0, 2)
                      .map((prompt) => (
                        <button
                          key={prompt}
                          onClick={() => handlePromptSelect(prompt)}
                          className="px-2 py-1 text-xs text-gray-500 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                        >
                          {prompt}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </>
          )}

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
              placeholder="Ask TAMI..."
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
              onClick={handleSend}
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
