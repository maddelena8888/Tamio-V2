import { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardContent } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Send, Mic, Bot, User, AlertTriangle, Sparkles, MessageSquare } from 'lucide-react';
import { sendChatMessageStreaming, formatConversationHistory } from '@/lib/api/tami';
import type { ChatMode, SuggestedAction } from '@/lib/api/types';
import ReactMarkdown from 'react-markdown';

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  mode?: ChatMode;
  suggestedActions?: SuggestedAction[];
  showScenarioBanner?: boolean;
  isStreaming?: boolean;
}

const examplePrompts = [
  { text: "What happens if I lose a client?", icon: AlertTriangle },
  { text: "How much runway do I have?", icon: Sparkles },
  { text: "What clients are most likely to pay late?", icon: MessageSquare },
];

// Animated typing indicator
const TypingIndicator = () => (
  <div className="flex items-center gap-1.5 py-1">
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce [animation-delay:-0.3s]" />
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce [animation-delay:-0.15s]" />
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce" />
  </div>
);

export default function Tami() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages]);

  const handleSend = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || !user) return;

    const userMessage: DisplayMessage = {
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const streamingMessage: DisplayMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setMessages((prev) => [...prev, streamingMessage]);

    const conversationHistory = formatConversationHistory(
      messages.map((m) => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      }))
    );

    await sendChatMessageStreaming(
      {
        user_id: user.id,
        message: text,
        conversation_history: conversationHistory,
        active_scenario_id: activeScenarioId,
      },
      (chunk) => {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            // Create new array with updated last message (immutable update)
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, content: lastMsg.content + chunk }
            ];
          }
          return prev;
        });
      },
      (event) => {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant') {
            // Create new array with updated last message (immutable update)
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                isStreaming: false,
                mode: event.mode,
                suggestedActions: event.ui_hints?.suggested_actions,
                showScenarioBanner: event.ui_hints?.show_scenario_banner,
              }
            ];
          }
          return prev;
        });

        if (event.mode === 'build_scenario') {
          const scenarioId = (event.context_summary as Record<string, string | undefined>)?.active_scenario_id;
          if (scenarioId) {
            setActiveScenarioId(scenarioId);
          }
        }

        setIsLoading(false);
        inputRef.current?.focus();
      },
      (error) => {
        console.error('Streaming error:', error);
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            // Create new array with updated last message (immutable update)
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                content: 'I encountered an error processing your request. Please try again.',
                isStreaming: false,
                mode: 'clarify' as const,
              }
            ];
          }
          return prev;
        });
        setIsLoading(false);
        inputRef.current?.focus();
      }
    );
  };

  const handleActionClick = async (action: SuggestedAction) => {
    if (action.action === 'none') return;

    if (action.action === 'call_tool') {
      if (action.tool_name && action.tool_args && Object.keys(action.tool_args).length > 0) {
        const toolMessage = `[Action: ${action.label}] Please execute: ${action.tool_name} with parameters: ${JSON.stringify(action.tool_args)}`;
        await handleSend(toolMessage);
      } else {
        await handleSend(action.label);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getModeLabel = (mode?: ChatMode): string => {
    switch (mode) {
      case 'explain_forecast': return 'Explaining';
      case 'suggest_scenarios': return 'Suggesting';
      case 'build_scenario': return 'Building Scenario';
      case 'goal_planning': return 'Planning';
      case 'clarify': return 'Clarifying';
      default: return '';
    }
  };

  const getModeIcon = (mode?: ChatMode) => {
    switch (mode) {
      case 'explain_forecast': return Sparkles;
      case 'suggest_scenarios': return AlertTriangle;
      case 'build_scenario': return MessageSquare;
      default: return null;
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-lime">
            <Bot className="h-6 w-6 text-gunmetal" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Ask TAMI</h1>
            <p className="text-sm text-muted-foreground">Your AI financial assistant</p>
          </div>
        </div>
        {activeScenarioId && (
          <Badge variant="outline" className="border-lime text-foreground bg-lime/10">
            <AlertTriangle className="h-3 w-3 mr-1" />
            Scenario Mode
          </Badge>
        )}
      </div>

      {/* Chat Area */}
      <NeuroCard className="flex-1 flex flex-col min-h-0 overflow-hidden p-0">
        <NeuroCardContent className="flex-1 flex flex-col min-h-0 p-0">
          <ScrollArea className="flex-1 h-full" ref={scrollAreaRef}>
            <div className="p-6">
              {messages.length === 0 ? (
                // Empty state with example prompts
                <div className="flex flex-col items-center justify-center min-h-[300px] text-center">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-lime to-lime/60 flex items-center justify-center mb-4 shadow-lg">
                    <Bot className="h-7 w-7 text-gunmetal" />
                  </div>
                  <h2 className="text-xl font-semibold mb-2">How can I help you today?</h2>
                  <p className="text-muted-foreground mb-6 max-w-md text-sm">
                    Ask about your cash flow, run what-if scenarios, or plan toward financial goals.
                  </p>
                  <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
                    {examplePrompts.map((prompt, index) => {
                      const Icon = prompt.icon;
                      return (
                        <Button
                          key={index}
                          variant="outline"
                          size="sm"
                          className="h-9 px-3 gap-2 hover:border-lime hover:bg-lime/10 transition-all"
                          onClick={() => handleSend(prompt.text)}
                        >
                          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-xs">{prompt.text}</span>
                        </Button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                // Message list
                <div className="space-y-6">
                  {messages.map((message, index) => (
                    <div key={index}>
                      <div
                        className={`flex gap-3 ${
                          message.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        {message.role === 'assistant' && (
                          <Avatar className="h-9 w-9 border-2 border-lime/30">
                            <AvatarFallback className="bg-primary text-primary-foreground">
                              <Bot className="h-4 w-4" />
                            </AvatarFallback>
                          </Avatar>
                        )}
                        <div
                          className={`max-w-[75%] ${
                            message.role === 'user'
                              ? 'bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-3 shadow-sm'
                              : 'space-y-3'
                          }`}
                        >
                          {message.role === 'assistant' && message.mode && !message.isStreaming && (
                            <div className="flex items-center gap-2 mb-2">
                              <Badge variant="secondary" className="text-xs px-2 py-0.5 bg-muted/80">
                                {(() => {
                                  const ModeIcon = getModeIcon(message.mode);
                                  return ModeIcon ? <ModeIcon className="h-3 w-3 mr-1" /> : null;
                                })()}
                                {getModeLabel(message.mode)}
                              </Badge>
                            </div>
                          )}

                          {message.role === 'assistant' && message.showScenarioBanner && (
                            <div className="p-3 bg-lime/10 border border-lime/30 rounded-lg text-sm mb-3 flex items-center gap-2">
                              <AlertTriangle className="h-4 w-4 text-lime" />
                              <span className="font-medium">Scenario editing mode active</span>
                            </div>
                          )}

                          {message.role === 'assistant' ? (
                            message.isStreaming && message.content === '' ? (
                              <TypingIndicator />
                            ) : (
                              <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-2 prose-headings:mt-4 prose-headings:mb-2 prose-li:my-0.5">
                                <ReactMarkdown>{message.content}</ReactMarkdown>
                              </div>
                            )
                          ) : (
                            <p className="leading-relaxed">{message.content}</p>
                          )}

                          {/* Suggested Actions */}
                          {message.role === 'assistant' &&
                            !message.isStreaming &&
                            message.suggestedActions &&
                            message.suggestedActions.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-border/50">
                                {message.suggestedActions.map((action, actionIndex) => (
                                  <Button
                                    key={actionIndex}
                                    variant={action.action === 'none' ? 'outline' : 'default'}
                                    size="sm"
                                    className={action.action !== 'none' ? 'bg-primary hover:bg-primary/90' : ''}
                                    onClick={() => handleActionClick(action)}
                                  >
                                    {action.label}
                                  </Button>
                                ))}
                              </div>
                            )}
                        </div>
                        {message.role === 'user' && (
                          <Avatar className="h-9 w-9 border-2 border-muted">
                            <AvatarFallback className="bg-muted">
                              <User className="h-4 w-4" />
                            </AvatarFallback>
                          </Avatar>
                        )}
                      </div>
                      {/* Separator between message pairs */}
                      {index < messages.length - 1 && message.role === 'assistant' && (
                        <Separator className="my-6 opacity-30" />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>
        </NeuroCardContent>

        {/* Input Area */}
        <div className="p-4 border-t bg-card/50 backdrop-blur-sm">
          <div className="flex gap-2 items-center">
            <div className="flex-1 relative">
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything..."
                disabled={isLoading}
                className="pr-10 h-11 rounded-xl bg-background border-muted-foreground/20 focus:border-lime focus:ring-lime/30"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              disabled
              title="Voice input coming soon"
              className="h-11 w-11 rounded-xl text-muted-foreground hover:text-foreground"
            >
              <Mic className="h-5 w-5" />
            </Button>
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              size="icon"
              className="h-11 w-11 rounded-xl bg-primary hover:bg-primary/90 transition-all"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </NeuroCard>
    </div>
  );
}
