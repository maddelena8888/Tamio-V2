import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardContent, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from '@/components/ui/chart';
import { ComposedChart, Area, XAxis, YAxis, CartesianGrid, Line, ReferenceDot } from 'recharts';
import {
  Users,
  UserPlus,
  UserMinus,
  TrendingUp,
  TrendingDown,
  Clock,
  Building,
  X,
  Save,
  CheckCircle2,
  ArrowRight,
  Send,
  AlertTriangle,
  Loader2,
  ExternalLink,
  Maximize2,
} from 'lucide-react';
import {
  getScenarios,
  getScenarioSuggestions,
  createScenario,
  buildScenario,
  getScenarioForecast,
  saveScenario,
  deleteScenario,
  getRules,
} from '@/lib/api/scenarios';
import { getClients, getExpenses } from '@/lib/api/data';
import { getForecast } from '@/lib/api/forecast';
import { sendChatMessageStreaming, formatConversationHistory } from '@/lib/api/tami';
import type {
  Scenario,
  ScenarioType,
  ScenarioSuggestion,
  ScenarioComparisonResponse,
  ForecastResponse,
  Client,
  ExpenseBucket,
  FinancialRule,
  ChatMode,
  SuggestedAction,
} from '@/lib/api/types';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';

// ============================================================================
// Types
// ============================================================================

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  mode?: ChatMode;
  suggestedActions?: SuggestedAction[];
  isStreaming?: boolean;
}

interface CollaboratorAvatar {
  id: string;
  name: string;
  initials: string;
  color: string;
  weekNumber?: number;
}

// ============================================================================
// Configuration
// ============================================================================

const scenarioTypeConfig: Record<ScenarioType, { label: string; icon: React.ElementType; description: string }> = {
  client_loss: { label: 'Client Loss', icon: UserMinus, description: 'Model losing a client' },
  client_gain: { label: 'Client Gain', icon: UserPlus, description: 'Model gaining a new client' },
  client_change: { label: 'Client Change', icon: Users, description: 'Model upsell/downsell' },
  hiring: { label: 'Hiring', icon: UserPlus, description: 'Model adding headcount' },
  firing: { label: 'Firing', icon: UserMinus, description: 'Model reducing headcount' },
  contractor_gain: { label: 'Contractor Gain', icon: Building, description: 'Model adding a contractor' },
  contractor_loss: { label: 'Contractor Loss', icon: Building, description: 'Model losing a contractor' },
  increased_expense: { label: 'Increased Expense', icon: TrendingUp, description: 'Model expense increase' },
  decreased_expense: { label: 'Decreased Expense', icon: TrendingDown, description: 'Model expense reduction' },
  payment_delay_in: { label: 'Payment Delay (In)', icon: Clock, description: 'Model delayed client payment' },
  payment_delay_out: { label: 'Payment Delay (Out)', icon: Clock, description: 'Model delayed vendor payment' },
};

const chartConfig = {
  base: { label: 'Base Forecast', color: 'var(--chart-1)' },
  scenario: { label: 'Scenario Forecast', color: 'var(--lime)' },
  buffer: { label: 'Cash Buffer', color: 'var(--tomato)' },
} satisfies ChartConfig;

// Mock collaborators for demo
const MOCK_COLLABORATORS: CollaboratorAvatar[] = [
  { id: '1', name: 'You', initials: 'M', color: 'bg-coral' },
  { id: '2', name: 'Sara', initials: 'S', color: 'bg-blue-500' },
  { id: '3', name: 'CFO', initials: 'C', color: 'bg-emerald-500' },
];

// ============================================================================
// Utility Functions
// ============================================================================

const formatCurrency = (value: number | string) => {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
};

const formatCompactCurrency = (value: number) => {
  if (Math.abs(value) >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1000) {
    return `$${Math.round(value / 1000)}K`;
  }
  return formatCurrency(value);
};

// Smart Y-axis formatter: uses K for thousands, M for millions
const formatYAxisValue = (value: number): string => {
  const absValue = Math.abs(value);

  if (absValue >= 1000000) {
    const millions = value / 1000000;
    const formatted = millions.toFixed(1);
    // Remove trailing .0 (e.g., "1.0" -> "1")
    return `$${formatted.replace(/\.0$/, '')}M`;
  }

  if (absValue >= 1000) {
    return `$${Math.round(value / 1000)}K`;
  }

  return `$${Math.round(value)}`;
};

// Get display amount for a client based on client type
const getClientDisplayAmount = (client: Client): string => {
  const config = client.billing_config;

  switch (client.client_type) {
    case 'project':
      // For projects, use total_value or sum of milestones
      if (config.total_value) return config.total_value;
      if (config.milestones && config.milestones.length > 0) {
        const total = config.milestones.reduce((sum, m) => sum + parseFloat(m.amount || '0'), 0);
        return total.toString();
      }
      return config.amount || '0';
    case 'usage':
      // For usage, use typical_amount or amount
      return config.typical_amount || config.amount || '0';
    default:
      // For retainer and mixed, use amount
      return config.amount || '0';
  }
};

// ============================================================================
// Suggested Prompt Type
// ============================================================================

interface SuggestedPrompt {
  id: string;
  label: string;
  query: string;
  icon: 'alert' | 'scenario' | 'forecast' | 'client';
  priority: 'high' | 'medium' | 'low';
  sourceType?: 'alert' | 'suggestion' | 'forecast';
  sourceId?: string;
}

// ============================================================================
// TAMI Chat Inline Component (Below Forecast)
// ============================================================================

interface TAMIChatInlineProps {
  userId: string;
  selectedWeek: number | null;
  forecastData: ForecastResponse | null;
  suggestions?: ScenarioSuggestion[];
  clients?: Client[];
}

function TAMIChatInline({ userId, selectedWeek, forecastData, suggestions = [], clients = [] }: TAMIChatInlineProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const expandedScrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Generate suggested prompts based on forecast data, alerts, and scenarios
  const suggestedPrompts: SuggestedPrompt[] = useMemo(() => {
    const prompts: SuggestedPrompt[] = [];

    // Add prompts from forecast data
    if (forecastData?.summary) {
      const lowestWeek = forecastData.summary.lowest_cash_week;
      const lowestAmount = forecastData.summary.lowest_cash_amount
        ? formatCompactCurrency(parseFloat(forecastData.summary.lowest_cash_amount))
        : null;

      if (lowestWeek && lowestAmount) {
        prompts.push({
          id: 'forecast-low',
          label: `Why does Week ${lowestWeek} dip to ${lowestAmount}?`,
          query: `Explain why Week ${lowestWeek} shows a cash dip to ${lowestAmount}`,
          icon: 'forecast',
          priority: 'high',
          sourceType: 'forecast',
        });
      }
    }

    // Add prompts from scenario suggestions (linked to alerts)
    suggestions.forEach((suggestion, index) => {
      if (prompts.length >= 3) return;
      if (suggestion.source_alert_id) {
        prompts.push({
          id: `alert-${suggestion.source_alert_id}`,
          label: suggestion.name,
          query: suggestion.name,
          icon: 'alert',
          priority: suggestion.priority === 'high' ? 'high' : 'medium',
          sourceType: 'alert',
          sourceId: suggestion.source_alert_id,
        });
      } else if (index < 2) {
        prompts.push({
          id: `suggestion-${index}`,
          label: suggestion.name,
          query: suggestion.name,
          icon: 'scenario',
          priority: suggestion.priority === 'high' ? 'high' : 'medium',
          sourceType: 'suggestion',
        });
      }
    });

    // Add client-related prompts for high-concentration clients
    const totalClientIncome = clients.reduce((sum, client) => {
      const amount = parseFloat(getClientDisplayAmount(client));
      return sum + amount;
    }, 0);

    clients.forEach((client) => {
      if (prompts.length >= 3) return;
      const clientAmount = parseFloat(getClientDisplayAmount(client));
      const concentration = totalClientIncome > 0 ? (clientAmount / totalClientIncome) * 100 : 0;

      if (concentration > 25) {
        prompts.push({
          id: `client-${client.id}`,
          label: `What if ${client.name} pays late?`,
          query: `What happens if ${client.name} pays 30 days late?`,
          icon: 'client',
          priority: concentration > 40 ? 'high' : 'medium',
          sourceType: 'suggestion',
        });
      }
    });

    // Default fallback prompts to ensure we always have 3
    const defaultPrompts: SuggestedPrompt[] = [
      {
        id: 'default-payroll',
        label: 'Can I make payroll if payments are delayed?',
        query: 'Can I make payroll if no payments come in for 2 weeks?',
        icon: 'alert',
        priority: 'high',
        sourceType: 'suggestion',
      },
      {
        id: 'default-hiring',
        label: 'Can we afford to hire someone new?',
        query: 'Can we afford to hire a new employee at $6,000/month?',
        icon: 'scenario',
        priority: 'medium',
        sourceType: 'suggestion',
      },
      {
        id: 'default-client-loss',
        label: 'What if we lose our biggest client?',
        query: 'What happens if we lose our biggest client?',
        icon: 'client',
        priority: 'medium',
        sourceType: 'suggestion',
      },
    ];

    // Fill in with defaults if we don't have 3 prompts
    let defaultIndex = 0;
    while (prompts.length < 3 && defaultIndex < defaultPrompts.length) {
      const defaultPrompt = defaultPrompts[defaultIndex];
      // Only add if we don't already have a similar prompt
      if (!prompts.some(p => p.id === defaultPrompt.id)) {
        prompts.push(defaultPrompt);
      }
      defaultIndex++;
    }

    // Sort by priority and return exactly 3
    return prompts
      .sort((a, b) => {
        const priorityOrder = { high: 0, medium: 1, low: 2 };
        return priorityOrder[a.priority] - priorityOrder[b.priority];
      })
      .slice(0, 3);
  }, [forecastData, suggestions, clients]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    if (expandedScrollRef.current) {
      expandedScrollRef.current.scrollTop = expandedScrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Handle week selection from chart
  useEffect(() => {
    if (selectedWeek !== null && forecastData) {
      const week = forecastData.weeks.find(w => w.week_number === selectedWeek);
      if (week) {
        const newMessage: DisplayMessage = {
          role: 'assistant',
          content: `**Week ${selectedWeek}** shows:\n- Starting: ${formatCurrency(week.starting_balance)}\n- Cash In: +${formatCurrency(week.cash_in)}\n- Cash Out: -${formatCurrency(week.cash_out)}\n- Ending: ${formatCurrency(week.ending_balance)}\n\nWould you like me to explain what's driving this week's numbers?`,
          timestamp: new Date(),
          mode: 'explain_forecast',
          suggestedActions: [
            { label: 'Why does this happen?', action: 'none', tool_name: null, tool_args: null },
            { label: 'Show mitigation options', action: 'none', tool_name: null, tool_args: null },
            { label: 'Run scenario', action: 'none', tool_name: null, tool_args: null },
          ],
        };
        setMessages(prev => [...prev, newMessage]);
      }
    }
  }, [selectedWeek, forecastData]);

  const handleSendMessage = useCallback(async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: DisplayMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    // Add streaming assistant message
    const streamingMessage: DisplayMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, streamingMessage]);

    try {
      await sendChatMessageStreaming(
        {
          user_id: userId,
          message: inputMessage,
          conversation_history: formatConversationHistory(messages),
          active_scenario_id: null,
        },
        // onChunk
        (chunk) => {
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (updated[lastIdx]?.isStreaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: updated[lastIdx].content + chunk,
              };
            }
            return updated;
          });
        },
        // onDone
        (event) => {
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (updated[lastIdx]?.isStreaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                isStreaming: false,
                mode: event.mode,
                suggestedActions: event.ui_hints?.suggested_actions,
              };
            }
            return updated;
          });
          setIsLoading(false);
        },
        // onError
        (error) => {
          console.error('Chat error:', error);
          setMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (updated[lastIdx]?.isStreaming) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                content: 'Sorry, I encountered an error. Please try again.',
                isStreaming: false,
              };
            }
            return updated;
          });
          setIsLoading(false);
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsLoading(false);
    }
  }, [inputMessage, isLoading, userId, messages]);

  const handleSuggestedAction = (action: SuggestedAction) => {
    setInputMessage(action.label);
    setTimeout(() => handleSendMessage(), 100);
  };

  const handleSuggestedPrompt = (prompt: SuggestedPrompt) => {
    // Directly set the user message and trigger send
    const userMessage: DisplayMessage = {
      role: 'user',
      content: prompt.query,
      timestamp: new Date(),
    };
    setMessages([userMessage]);
    setInputMessage('');
    setIsLoading(true);

    // Add streaming assistant message
    const streamingMessage: DisplayMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, streamingMessage]);

    // Send the message
    sendChatMessageStreaming(
      {
        user_id: userId,
        message: prompt.query,
        conversation_history: [],
        active_scenario_id: null,
      },
      (chunk) => {
        setMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (updated[lastIdx]?.isStreaming) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: updated[lastIdx].content + chunk,
            };
          }
          return updated;
        });
      },
      (event) => {
        setMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (updated[lastIdx]?.isStreaming) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              isStreaming: false,
              mode: event.mode,
              suggestedActions: event.ui_hints?.suggested_actions,
            };
          }
          return updated;
        });
        setIsLoading(false);
      },
      (error) => {
        console.error('Chat error:', error);
        setMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (updated[lastIdx]?.isStreaming) {
            updated[lastIdx] = {
              ...updated[lastIdx],
              content: 'Sorry, I encountered an error. Please try again.',
              isStreaming: false,
            };
          }
          return updated;
        });
        setIsLoading(false);
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Get styling based on priority for glassmorphic cards - subtle solid backgrounds
  const getPromptStyles = (priority: SuggestedPrompt['priority']) => {
    switch (priority) {
      case 'high':
        return {
          bg: 'bg-red-50/70',
          border: 'border-red-200/50',
          hoverBorder: 'hover:border-red-300/70',
        };
      case 'medium':
        return {
          bg: 'bg-amber-50/70',
          border: 'border-amber-200/50',
          hoverBorder: 'hover:border-amber-300/70',
        };
      case 'low':
        return {
          bg: 'bg-lime/15',
          border: 'border-lime/30',
          hoverBorder: 'hover:border-lime/50',
        };
      default:
        return {
          bg: 'bg-white/50',
          border: 'border-white/40',
          hoverBorder: 'hover:border-white/60',
        };
    }
  };

  // Render message content (shared between inline and expanded views)
  const renderMessage = (message: DisplayMessage, index: number) => (
    <div key={index} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[80%] rounded-2xl px-4 py-3 text-sm',
          message.role === 'user'
            ? 'bg-gunmetal text-white'
            : 'bg-white/60 backdrop-blur-sm border border-white/40 text-gunmetal'
        )}
      >
        {message.role === 'assistant' ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            {message.isStreaming && (
              <span className="inline-flex items-center gap-1 ml-1">
                <span className="w-1.5 h-1.5 bg-coral rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-1.5 h-1.5 bg-coral rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-1.5 h-1.5 bg-coral rounded-full animate-bounce" />
              </span>
            )}
          </div>
        ) : (
          message.content
        )}

        {/* Suggested Actions */}
        {message.suggestedActions && message.suggestedActions.length > 0 && !message.isStreaming && (
          <div className="flex flex-wrap gap-2 mt-3">
            {message.suggestedActions.map((action, actionIndex) => (
              <button
                key={actionIndex}
                onClick={() => handleSuggestedAction(action)}
                className={cn(
                  'px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                  actionIndex === 0
                    ? 'bg-coral text-white hover:bg-coral/90'
                    : 'bg-white/80 backdrop-blur-sm border border-white/40 text-gunmetal hover:bg-white'
                )}
              >
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  // Render input section (shared between inline and expanded views)
  const renderInput = () => (
    <div className="flex items-center gap-3">
      <Input
        ref={inputRef}
        value={inputMessage}
        onChange={(e) => setInputMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about any week or scenario..."
        className="flex-1 bg-white/50 backdrop-blur-sm border-white/40 focus:border-coral/40 focus:ring-coral/20"
        disabled={isLoading}
      />
      <Button
        onClick={handleSendMessage}
        disabled={!inputMessage.trim() || isLoading}
        className="bg-gradient-to-r from-coral to-coral/80 hover:from-coral/90 hover:to-coral/70 text-white px-6 shadow-md"
      >
        {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
      </Button>
    </div>
  );

  return (
    <>
      {/* Inline Chat View */}
      <div className="rounded-2xl bg-white/30 backdrop-blur-xl border border-white/40 p-8 shadow-lg shadow-black/5 min-h-[280px]">
        {/* Header with expand button */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-coral to-coral/70 flex items-center justify-center shadow-md">
              <span className="text-white text-base font-bold">T</span>
            </div>
            <div>
              <h3 className="text-base font-semibold text-gunmetal">Chat with TAMI</h3>
              <p className="text-xs text-muted-foreground">Ask about forecast details or explore scenarios</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsExpanded(true)}
            className="h-8 w-8 text-muted-foreground hover:text-gunmetal"
            title="Expand chat"
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>

        {/* Suggested Prompts - shown when no messages */}
        {messages.length === 0 && suggestedPrompts.length > 0 && (
          <div className="mb-5">
            <p className="text-xs text-muted-foreground mb-3">Suggested Starters</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {suggestedPrompts.map((prompt) => {
                const styles = getPromptStyles(prompt.priority);
                return (
                  <button
                    key={prompt.id}
                    onClick={() => handleSuggestedPrompt(prompt)}
                    disabled={isLoading}
                    className={cn(
                      'relative flex items-center p-4 rounded-xl text-left transition-all duration-300 group disabled:opacity-50',
                      'backdrop-blur-sm border',
                      styles.bg,
                      styles.border,
                      styles.hoverBorder,
                      'hover:shadow-md hover:scale-[1.02]'
                    )}
                  >
                    <span className="text-sm font-medium text-gunmetal/90 group-hover:text-gunmetal line-clamp-2">
                      {prompt.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Messages - scrollable area with max height */}
        {messages.length > 0 && (
          <div
            ref={scrollRef}
            className="max-h-[300px] overflow-y-auto mb-5 space-y-3 pr-2"
          >
            {messages.map(renderMessage)}
          </div>
        )}

        {/* Input */}
        {renderInput()}
      </div>

      {/* Expanded Fullscreen Chat Modal */}
      <Dialog open={isExpanded} onOpenChange={setIsExpanded}>
        <DialogContent className="max-w-4xl h-[85vh] flex flex-col p-0">
          <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-coral to-coral/70 flex items-center justify-center shadow-md">
                <span className="text-white text-base font-bold">T</span>
              </div>
              <DialogTitle className="text-lg font-semibold">Chat with TAMI</DialogTitle>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-hidden flex flex-col px-6 py-4">
            {/* Suggested Prompts in expanded view */}
            {messages.length === 0 && suggestedPrompts.length > 0 && (
              <div className="mb-5">
                <p className="text-xs text-muted-foreground mb-3">Suggested Starters</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {suggestedPrompts.map((prompt) => {
                    const styles = getPromptStyles(prompt.priority);
                    return (
                      <button
                        key={prompt.id}
                        onClick={() => handleSuggestedPrompt(prompt)}
                        disabled={isLoading}
                        className={cn(
                          'relative flex items-center p-4 rounded-xl text-left transition-all duration-300 group disabled:opacity-50',
                          'backdrop-blur-sm border',
                          styles.bg,
                          styles.border,
                          styles.hoverBorder,
                          'hover:shadow-md hover:scale-[1.02]'
                        )}
                      >
                        <span className="text-sm font-medium text-gunmetal/90 group-hover:text-gunmetal line-clamp-2">
                          {prompt.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Messages area - scrollable */}
            <div
              ref={expandedScrollRef}
              className="flex-1 overflow-y-auto space-y-3 pr-2"
            >
              {messages.map(renderMessage)}
            </div>

            {/* Input - fixed at bottom */}
            <div className="pt-4 border-t mt-4">
              {renderInput()}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ============================================================================
// Floating Notification Component
// ============================================================================

interface FloatingNotificationProps {
  show: boolean;
  onDismiss: () => void;
  onAction: () => void;
}

function FloatingNotification({ show, onDismiss, onAction }: FloatingNotificationProps) {
  if (!show) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
      <div className="bg-white/70 backdrop-blur-xl rounded-2xl shadow-xl border border-white/40 p-4 max-w-sm">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-lime/40 to-lime/20 flex items-center justify-center flex-shrink-0">
            <TrendingUp className="w-5 h-5 text-lime-dark" />
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gunmetal text-sm">Quick heads up</h4>
            <p className="text-sm text-muted-foreground mt-1">
              HealthTech just paid their invoice early! This improves your Week 5 buffer by $8K.
            </p>
            <div className="flex items-center gap-2 mt-3">
              <Button size="sm" onClick={onAction} className="bg-gradient-to-r from-coral to-coral/80 hover:from-coral/90 hover:to-coral/70 text-white text-xs shadow-sm">
                View Update
              </Button>
              <Button size="sm" variant="ghost" onClick={onDismiss} className="text-xs text-muted-foreground hover:text-gunmetal">
                Later
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Scenarios Component
// ============================================================================

export default function Scenarios() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  // Data state
  const [savedScenarios, setSavedScenarios] = useState<Scenario[]>([]);
  const [suggestions, setSuggestions] = useState<ScenarioSuggestion[]>([]);
  const [baseForecast, setBaseForecast] = useState<ForecastResponse | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [expenses, setExpenses] = useState<ExpenseBucket[]>([]);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [savedScenariosDialogOpen, setSavedScenariosDialogOpen] = useState(false);
  const [appliedScenarios, setAppliedScenarios] = useState<string[]>([]);

  // Chart interaction state
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [timePeriod, setTimePeriod] = useState<'13' | '26' | '52'>('13');

  // URL parameter for highlighting specific week from navigation
  const highlightWeekParam = searchParams.get('week');
  const [highlightedWeek, setHighlightedWeek] = useState<number | null>(null);

  // Set highlighted week from URL parameter
  useEffect(() => {
    if (highlightWeekParam) {
      const weekNum = parseInt(highlightWeekParam);
      if (!isNaN(weekNum)) {
        setHighlightedWeek(weekNum);
        setSelectedWeek(weekNum);
        // Clear highlight after 5 seconds
        const timer = setTimeout(() => setHighlightedWeek(null), 5000);
        return () => clearTimeout(timer);
      }
    }
  }, [highlightWeekParam]);

  // Scenario builder state
  const [scenarioType, setScenarioType] = useState<ScenarioType | ''>('');
  const [scenarioName, setScenarioName] = useState('');
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparisonResponse | null>(null);

  // Form fields
  const [selectedClient, setSelectedClient] = useState('');
  const [selectedExpense, setSelectedExpense] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [amount, setAmount] = useState('');
  const [delayDays, setDelayDays] = useState('');
  const [isBuildingScenario, setIsBuildingScenario] = useState(false);
  const [buildError, setBuildError] = useState<string | null>(null);

  // Notification state
  const [showNotification, setShowNotification] = useState(false);

  // Show notification after 3 seconds (demo)
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowNotification(true);
    }, 3000);
    return () => clearTimeout(timer);
  }, []);

  // Fetch initial data
  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const [scenariosData, suggestionsData, forecastData, clientsData, expensesData, rulesData] = await Promise.all([
          getScenarios(user.id, 'saved').catch(() => []),
          getScenarioSuggestions(user.id).catch(() => ({ suggestions: [] })),
          getForecast(user.id, parseInt(timePeriod)).catch(() => null),
          getClients(user.id).catch(() => []),
          getExpenses(user.id).catch(() => []),
          getRules(user.id).catch(() => []),
        ]);

        setSavedScenarios(scenariosData);
        setSuggestions(suggestionsData.suggestions || []);
        setBaseForecast(forecastData);
        setClients(clientsData.filter((c) => c.status === 'active'));
        setExpenses(expensesData);
        setRules(rulesData);

        // Handle URL parameters for pre-filling scenario from alerts
        const typeParam = searchParams.get('type');
        const clientParam = searchParams.get('client');
        const amountParam = searchParams.get('amount');
        const delayParam = searchParams.get('delay');
        const fromAlertParam = searchParams.get('from_alert');
        const alertTitleParam = searchParams.get('alert_title');

        if (typeParam && typeParam in scenarioTypeConfig) {
          setScenarioType(typeParam as ScenarioType);

          // Set scenario name based on alert title or default
          if (alertTitleParam) {
            setScenarioName(`What-if: ${alertTitleParam}`);
          } else {
            setScenarioName(`${scenarioTypeConfig[typeParam as ScenarioType].label} Scenario`);
          }

          // Pre-fill client if provided
          if (clientParam) {
            setSelectedClient(clientParam);
          }

          // Pre-fill amount if provided
          if (amountParam) {
            setAmount(amountParam);
          }

          // Pre-fill delay days if provided
          if (delayParam) {
            setDelayDays(delayParam);
          }

          // Set effective date to today if coming from an alert
          if (fromAlertParam) {
            setEffectiveDate(new Date().toISOString().split('T')[0]);
          }
        }
      } catch (error) {
        console.error('Failed to fetch scenario data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user, searchParams, timePeriod]);

  // Handlers
  const handleStartScenario = (type: ScenarioType, suggestion?: ScenarioSuggestion) => {
    setScenarioType(type);
    setScenarioName(suggestion?.name || `${scenarioTypeConfig[type].label} Scenario`);
    setComparison(null);

    if (suggestion?.prefill_params) {
      const params = suggestion.prefill_params as Record<string, unknown>;
      if (params.client_id) setSelectedClient(params.client_id as string);
      if (params.effective_date) setEffectiveDate(params.effective_date as string);
      if (params.amount) setAmount(String(params.amount));
      if (params.delay_days) setDelayDays(String(params.delay_days));
    } else {
      setSelectedClient('');
      setEffectiveDate('');
      setAmount('');
      setDelayDays('');
    }
  };

  const handleBuildScenario = async () => {
    if (!user || !scenarioType) return;

    setIsBuildingScenario(true);
    setBuildError(null);

    const buildScopeConfig = () => {
      if (selectedClient) return { client_id: selectedClient };
      if (selectedExpense) return { bucket_id: selectedExpense };
      return {};
    };

    try {
      const scenario = await createScenario({
        user_id: user.id,
        name: scenarioName,
        scenario_type: scenarioType,
        entry_path: 'user_defined',
        scope_config: buildScopeConfig(),
        parameters: {
          effective_date: effectiveDate || new Date().toISOString().split('T')[0],
          amount,
          delay_days: delayDays ? parseInt(delayDays) : undefined,
        },
      });

      setActiveScenario(scenario);
      await buildScenario(scenario.id);
      const comparisonData = await getScenarioForecast(scenario.id);
      setComparison(comparisonData);
      toast.success('Scenario applied to forecast', {
        description: `See the impact of "${scenarioName}" on your cash flow.`,
        duration: 4000,
      });
    } catch (error) {
      console.error('Failed to build scenario:', error);
      setBuildError(error instanceof Error ? error.message : 'Failed to build scenario. Please try again.');
    } finally {
      setIsBuildingScenario(false);
    }
  };

  const handleSaveScenario = async () => {
    if (!activeScenario) return;

    try {
      await saveScenario(activeScenario.id);
      setSavedScenarios([...savedScenarios, { ...activeScenario, status: 'saved' }]);
      setActiveScenario(null);
      setComparison(null);
      resetForm();
    } catch (error) {
      console.error('Failed to save scenario:', error);
    }
  };

  const handleDiscardScenario = async () => {
    if (activeScenario) {
      await deleteScenario(activeScenario.id).catch(() => {});
    }
    setActiveScenario(null);
    setComparison(null);
    resetForm();
  };

  const resetForm = () => {
    setScenarioType('');
    setScenarioName('');
    setSelectedClient('');
    setSelectedExpense('');
    setEffectiveDate('');
    setAmount('');
    setDelayDays('');
  };

  const toggleAppliedScenario = (scenarioId: string) => {
    setAppliedScenarios((prev) =>
      prev.includes(scenarioId) ? prev.filter((id) => id !== scenarioId) : [...prev, scenarioId]
    );
  };

  const handleChartClick = (weekNumber: number) => {
    setSelectedWeek(weekNumber);
    toast.success(`Week ${weekNumber} added to chat`, {
      duration: 2000,
      position: 'bottom-center',
    });
  };

  // Helper functions
  const getInferredClientAmount = (): string | null => {
    if (scenarioType !== 'client_loss' || !selectedClient) return null;
    const client = clients.find((c) => c.id === selectedClient);
    if (!client) return null;
    const amount = getClientDisplayAmount(client);
    return amount !== '0' ? amount : null;
  };

  const getAmountLabel = (): string => {
    switch (scenarioType) {
      case 'client_gain':
      case 'hiring':
      case 'contractor_gain':
      case 'increased_expense':
        return 'Monthly Amount ($)';
      case 'client_change':
        return 'Change Amount (+/-)';
      case 'firing':
      case 'contractor_loss':
      case 'decreased_expense':
        return 'Monthly Reduction ($)';
      default:
        return 'Amount ($)';
    }
  };

  const requiresAmountInput = (): boolean => {
    return [
      'client_gain',
      'hiring',
      'contractor_gain',
      'increased_expense',
      'client_change',
      'firing',
      'contractor_loss',
      'decreased_expense',
    ].includes(scenarioType);
  };

  // Generate suggested scenarios
  // Generate diverse suggested scenarios based on actual business data
  // Includes: payment delays, hiring, expense increases, client loss, contractor changes
  // All suggestions are framed around protecting the buffer with specific names/amounts
  const generateSuggestedScenarios = (): ScenarioSuggestion[] => {
    const allPossibleSuggestions: ScenarioSuggestion[] = [];

    // Calculate total client income for concentration analysis
    const totalClientIncome = clients.reduce((sum, client) => {
      const amount = parseFloat(getClientDisplayAmount(client));
      return sum + amount;
    }, 0);

    // Sort clients by revenue for targeted suggestions
    const sortedClients = [...clients].sort((a, b) => {
      const amountA = parseFloat(getClientDisplayAmount(a));
      const amountB = parseFloat(getClientDisplayAmount(b));
      return amountB - amountA;
    });

    // Sort expenses by amount for targeted suggestions
    const sortedExpenses = [...expenses].sort((a, b) => {
      const amountA = parseFloat(a.monthly_amount || '0');
      const amountB = parseFloat(b.monthly_amount || '0');
      return amountB - amountA;
    });

    // Calculate monthly burn and buffer for impact calculations
    const monthlyBurn = baseForecast?.summary?.total_cash_out
      ? parseFloat(baseForecast.summary.total_cash_out) / 3
      : 50000;
    const currentBuffer = parseFloat(baseForecast?.starting_cash || '0');
    const bufferRuleConfig = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
    const targetMonths = (bufferRuleConfig?.threshold_config as { months?: number })?.months || 3;

    // Helper to format currency
    const fmtCurrency = (val: number) => val.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

    // ===========================================
    // CATEGORY 1: Client Payment Delays
    // ===========================================
    if (sortedClients.length > 0) {
      const topClient = sortedClients[0];
      const clientAmount = parseFloat(getClientDisplayAmount(topClient));
      const concentration = totalClientIncome > 0 ? (clientAmount / totalClientIncome) * 100 : 0;
      const weeksImpact = monthlyBurn > 0 ? (clientAmount / (monthlyBurn / 4)).toFixed(1) : '2';
      const bufferImpactPct = currentBuffer > 0 ? ((clientAmount / currentBuffer) * 100).toFixed(0) : '15';

      allPossibleSuggestions.push({
        scenario_type: 'payment_delay_in',
        name: `What if ${topClient.name} pays 14 days late?`,
        description: `Delays ${fmtCurrency(clientAmount)} for 2 weeks`,
        prefill_params: { client_id: topClient.id, delay_days: 14 },
        priority: concentration > 30 ? 'high' : 'medium',
        buffer_impact: `-${weeksImpact} weeks buffer`,
        buffer_impact_pct: parseInt(bufferImpactPct),
        risk_context: concentration > 25
          ? `${topClient.name} is ${concentration.toFixed(0)}% of revenue`
          : `Tests buffer resilience to payment timing`,
      });
    }

    // ===========================================
    // CATEGORY 2: Hiring Scenarios (Role-Specific)
    // ===========================================
    // Sales hire - common growth scenario
    const salesHireCost = 7500; // Base + commission structure
    const salesMonthsImpact = monthlyBurn > 0 ? ((salesHireCost * 12) / monthlyBurn).toFixed(1) : '1.8';
    const salesBufferPct = currentBuffer > 0 ? ((salesHireCost * 3 / currentBuffer) * 100).toFixed(0) : '12';

    allPossibleSuggestions.push({
      scenario_type: 'hiring',
      name: 'Can we hire a new sales rep?',
      description: `Adds ${fmtCurrency(salesHireCost)}/month (base + commission)`,
      prefill_params: { amount: salesHireCost, effective_date: new Date().toISOString().split('T')[0] },
      priority: 'medium',
      buffer_impact: `-${salesMonthsImpact} months buffer/year`,
      buffer_impact_pct: parseInt(salesBufferPct),
      risk_context: `Revenue impact typically shows in 3-6 months`,
    });

    // Engineer hire - different cost structure
    const engHireCost = 10000;
    const engMonthsImpact = monthlyBurn > 0 ? ((engHireCost * 12) / monthlyBurn).toFixed(1) : '2.4';
    const engBufferPct = currentBuffer > 0 ? ((engHireCost * 3 / currentBuffer) * 100).toFixed(0) : '15';

    allPossibleSuggestions.push({
      scenario_type: 'hiring',
      name: 'Can we hire a senior engineer?',
      description: `Adds ${fmtCurrency(engHireCost)}/month to payroll`,
      prefill_params: { amount: engHireCost, effective_date: new Date().toISOString().split('T')[0] },
      priority: 'medium',
      buffer_impact: `-${engMonthsImpact} months buffer/year`,
      buffer_impact_pct: parseInt(engBufferPct),
      risk_context: `Check if buffer stays above ${targetMonths} months`,
    });

    // ===========================================
    // CATEGORY 3: Expense Increases (Specific Vendors/Categories)
    // ===========================================
    // Find specific expense categories for realistic suggestions
    const softwareExpense = sortedExpenses.find(e =>
      e.name.toLowerCase().includes('software') ||
      e.name.toLowerCase().includes('aws') ||
      e.name.toLowerCase().includes('cloud') ||
      e.name.toLowerCase().includes('saas')
    );
    const contractorExpense = sortedExpenses.find(e =>
      e.name.toLowerCase().includes('contractor') ||
      e.name.toLowerCase().includes('freelance') ||
      e.name.toLowerCase().includes('consulting')
    );
    const marketingExpense = sortedExpenses.find(e =>
      e.name.toLowerCase().includes('marketing') ||
      e.name.toLowerCase().includes('advertising') ||
      e.name.toLowerCase().includes('ads')
    );

    // Software/Cloud cost increase
    if (softwareExpense) {
      const currentAmount = parseFloat(softwareExpense.monthly_amount || '0');
      const increaseAmount = Math.round(currentAmount * 0.25); // 25% increase
      const newAmount = currentAmount + increaseAmount;
      const impactPct = currentBuffer > 0 ? ((increaseAmount * 12 / currentBuffer) * 100).toFixed(0) : '8';

      allPossibleSuggestions.push({
        scenario_type: 'increased_expense',
        name: `What if ${softwareExpense.name} increases 25%?`,
        description: `${fmtCurrency(currentAmount)} → ${fmtCurrency(newAmount)}/month`,
        prefill_params: { bucket_id: softwareExpense.id, amount: increaseAmount },
        priority: 'medium',
        buffer_impact: `-${fmtCurrency(increaseAmount * 12)}/year`,
        buffer_impact_pct: parseInt(impactPct),
        risk_context: `Cloud costs often scale with growth`,
      });
    } else {
      // Fallback: generic software cost increase
      const genericIncrease = 1500;
      const impactPct = currentBuffer > 0 ? ((genericIncrease * 12 / currentBuffer) * 100).toFixed(0) : '8';

      allPossibleSuggestions.push({
        scenario_type: 'increased_expense',
        name: 'What if software costs increase by $1,500/mo?',
        description: `Common with scaling SaaS tools and cloud usage`,
        prefill_params: { amount: genericIncrease },
        priority: 'low',
        buffer_impact: `-${fmtCurrency(genericIncrease * 12)}/year`,
        buffer_impact_pct: parseInt(impactPct),
        risk_context: `Plan for annual vendor price increases`,
      });
    }

    // Contractor cost increase
    if (contractorExpense) {
      const currentAmount = parseFloat(contractorExpense.monthly_amount || '0');
      const increaseAmount = Math.round(currentAmount * 0.20); // 20% rate increase
      const newAmount = currentAmount + increaseAmount;
      const impactPct = currentBuffer > 0 ? ((increaseAmount * 12 / currentBuffer) * 100).toFixed(0) : '6';

      allPossibleSuggestions.push({
        scenario_type: 'increased_expense',
        name: `What if contractor rates increase 20%?`,
        description: `${fmtCurrency(currentAmount)} → ${fmtCurrency(newAmount)}/month`,
        prefill_params: { bucket_id: contractorExpense.id, amount: increaseAmount },
        priority: 'medium',
        buffer_impact: `-${fmtCurrency(increaseAmount * 12)}/year`,
        buffer_impact_pct: parseInt(impactPct),
        risk_context: `Contractor rate renewals coming up`,
      });
    }

    // ===========================================
    // CATEGORY 4: Client Loss Scenarios
    // ===========================================
    if (sortedClients.length > 0) {
      const topClient = sortedClients[0];
      const clientAmount = parseFloat(getClientDisplayAmount(topClient));
      const concentration = totalClientIncome > 0 ? (clientAmount / totalClientIncome) * 100 : 0;
      const monthsImpact = monthlyBurn > 0 ? (clientAmount / monthlyBurn).toFixed(1) : '2';
      const bufferImpactPct = currentBuffer > 0 ? ((clientAmount * 3 / currentBuffer) * 100).toFixed(0) : '25';

      allPossibleSuggestions.push({
        scenario_type: 'client_loss',
        name: `What if we lose ${topClient.name}?`,
        description: `Loses ${fmtCurrency(clientAmount)}/month revenue`,
        prefill_params: { client_id: topClient.id },
        priority: concentration > 25 ? 'high' : 'medium',
        buffer_impact: `-${monthsImpact} months buffer`,
        buffer_impact_pct: parseInt(bufferImpactPct),
        risk_context: concentration > 25
          ? `High concentration risk (${concentration.toFixed(0)}% of revenue)`
          : `Stress test your runway`,
      });
    }

    // ===========================================
    // CATEGORY 5: Contractor Changes
    // ===========================================
    // Adding a contractor
    const contractorCost = 5000;
    const contractorImpact = monthlyBurn > 0 ? ((contractorCost * 12) / monthlyBurn).toFixed(1) : '1.2';
    const contractorPct = currentBuffer > 0 ? ((contractorCost * 3 / currentBuffer) * 100).toFixed(0) : '8';

    allPossibleSuggestions.push({
      scenario_type: 'contractor_gain',
      name: 'Can we bring on a new contractor?',
      description: `Adds ${fmtCurrency(contractorCost)}/month for specialized work`,
      prefill_params: { amount: contractorCost, effective_date: new Date().toISOString().split('T')[0] },
      priority: 'low',
      buffer_impact: `-${contractorImpact} months buffer/year`,
      buffer_impact_pct: parseInt(contractorPct),
      risk_context: `Flexible capacity vs. full-time hire`,
    });

    // ===========================================
    // CATEGORY 6: Marketing/Growth Investment
    // ===========================================
    if (marketingExpense) {
      const currentAmount = parseFloat(marketingExpense.monthly_amount || '0');
      const increaseAmount = Math.round(currentAmount * 0.50); // 50% increase for campaign
      const impactPct = currentBuffer > 0 ? ((increaseAmount * 3 / currentBuffer) * 100).toFixed(0) : '10';

      allPossibleSuggestions.push({
        scenario_type: 'increased_expense',
        name: `What if we increase marketing spend 50%?`,
        description: `Boost ${fmtCurrency(currentAmount)} → ${fmtCurrency(currentAmount + increaseAmount)}/month`,
        prefill_params: { bucket_id: marketingExpense.id, amount: increaseAmount },
        priority: 'low',
        buffer_impact: `-${fmtCurrency(increaseAmount * 3)} over 3 months`,
        buffer_impact_pct: parseInt(impactPct),
        risk_context: `Growth investment with delayed ROI`,
      });
    }

    // ===========================================
    // CATEGORY 7: Vendor Payment Delays (Outbound)
    // ===========================================
    if (sortedExpenses.length > 0) {
      const topExpense = sortedExpenses[0];
      const expenseAmount = parseFloat(topExpense.monthly_amount || '0');
      const weeksGained = monthlyBurn > 0 ? (expenseAmount / (monthlyBurn / 4)).toFixed(1) : '1';

      allPossibleSuggestions.push({
        scenario_type: 'payment_delay_out',
        name: `What if we delay ${topExpense.name} payment?`,
        description: `Delays ${fmtCurrency(expenseAmount)} outflow by 2 weeks`,
        prefill_params: { bucket_id: topExpense.id, delay_days: 14 },
        priority: 'low',
        buffer_impact: `+${weeksGained} weeks buffer temporarily`,
        buffer_impact_pct: 0,
        risk_context: `Emergency cash flow management option`,
      });
    }

    // ===========================================
    // Select diverse mix of scenarios (prioritize variety)
    // ===========================================
    const selectedSuggestions: ScenarioSuggestion[] = [];
    const usedTypes = new Set<string>();

    // First pass: pick highest priority from each unique type
    const priorityOrder = { high: 0, medium: 1, low: 2 };
    const sortedByPriority = [...allPossibleSuggestions].sort((a, b) =>
      priorityOrder[a.priority || 'low'] - priorityOrder[b.priority || 'low']
    );

    for (const suggestion of sortedByPriority) {
      if (selectedSuggestions.length >= 3) break;
      if (!usedTypes.has(suggestion.scenario_type)) {
        selectedSuggestions.push(suggestion);
        usedTypes.add(suggestion.scenario_type);
      }
    }

    // Second pass: fill remaining slots with highest priority items
    for (const suggestion of sortedByPriority) {
      if (selectedSuggestions.length >= 3) break;
      if (!selectedSuggestions.includes(suggestion)) {
        selectedSuggestions.push(suggestion);
      }
    }

    return selectedSuggestions.slice(0, 3);
  };

  const allSuggestions = suggestions.length > 0 ? suggestions : generateSuggestedScenarios();

  // Calculate metrics from backend data (consistent with Dashboard)
  const hasData = baseForecast && baseForecast.weeks && baseForecast.weeks.length > 0;

  const bufferRule = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
  const targetBufferMonths = (bufferRule?.threshold_config as { months?: number })?.months || 3;

  const totalCashOut = baseForecast?.summary?.total_cash_out
    ? parseFloat(baseForecast.summary.total_cash_out)
    : 0;
  const totalCashIn = baseForecast?.summary?.total_cash_in
    ? parseFloat(baseForecast.summary.total_cash_in)
    : 0;
  const monthlyExpenses = totalCashOut / 3;
  const monthlyIncome = totalCashIn / 3;
  const bufferAmount = monthlyExpenses * targetBufferMonths;

  // Get values from backend summary
  const cashPosition = parseFloat(baseForecast?.starting_cash || '0');
  const runwayWeeks = baseForecast?.summary?.runway_weeks || 0;
  const lowestCashWeek = baseForecast?.summary?.lowest_cash_week || 0;
  const lowestCashAmount = parseFloat(baseForecast?.summary?.lowest_cash_amount || '0');

  // Suppress unused variable warnings - available for future use
  void runwayWeeks;
  void lowestCashWeek;
  void lowestCashAmount;

  // Calculate buffer coverage in months (consistent with Dashboard)
  const bufferCoverageMonths = monthlyExpenses > 0
    ? Math.max(0, lowestCashAmount / monthlyExpenses)
    : (lowestCashAmount > 0 ? 99 : 0);

  // Determine risk level based on buffer coverage
  // High: less than 1 month, Medium: 1-3 months, Low: 3+ months
  const riskLevel = !hasData ? 'Unknown'
    : bufferCoverageMonths < 1 ? 'High'
    : bufferCoverageMonths < targetBufferMonths ? 'Medium'
    : 'Low';

  // Chart data
  const chartData = comparison
    ? comparison.base_forecast?.weeks.map((baseWeek, index) => {
        const scenarioWeek = comparison.scenario_forecast?.weeks[index];
        return {
          week: `Week ${baseWeek.week_number}`,
          weekNumber: baseWeek.week_number,
          base: parseFloat(baseWeek.ending_balance),
          scenario: scenarioWeek ? parseFloat(scenarioWeek.ending_balance) : parseFloat(baseWeek.ending_balance),
          buffer: bufferAmount,
          cashIn: parseFloat(baseWeek.cash_in),
          cashOut: parseFloat(baseWeek.cash_out),
          isHighlighted: baseWeek.week_number === highlightedWeek,
        };
      })
    : baseForecast?.weeks.map((week) => ({
        week: `Week ${week.week_number}`,
        weekNumber: week.week_number,
        base: parseFloat(week.ending_balance),
        scenario: null,
        buffer: bufferAmount,
        cashIn: parseFloat(week.cash_in),
        cashOut: parseFloat(week.cash_out),
        isHighlighted: week.week_number === highlightedWeek,
      })) || [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-20 w-full" />
        <div className="grid grid-cols-3 gap-5">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
        <Skeleton className="h-[500px]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header with Active Collaborators */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-gunmetal">Forecast & Scenarios</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Active now</span>
          <div className="flex -space-x-1.5">
            {MOCK_COLLABORATORS.map((collab) => (
              <Avatar key={collab.id} className="w-6 h-6 border-2 border-white">
                <AvatarFallback className={cn(collab.color, 'text-white text-[10px] font-medium')}>
                  {collab.initials}
                </AvatarFallback>
              </Avatar>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Current Position */}
        <NeuroCard className="p-6">
          <div className="text-center">
            <div className="text-4xl font-bold text-gunmetal">{formatCompactCurrency(cashPosition)}</div>
            <div className="text-sm font-medium text-muted-foreground mt-2">Current Position</div>
            <div className="flex items-center justify-center gap-1 mt-2">
              <TrendingUp className="h-3.5 w-3.5 text-lime-dark" />
              <span className="text-xs font-medium text-lime-dark">+5.9% (30D)</span>
            </div>
          </div>
        </NeuroCard>

        {/* Income (30D) */}
        <NeuroCard className="p-6">
          <div className="text-center">
            <div className="text-4xl font-bold text-lime-dark">
              {!hasData ? '--' : `+${formatCompactCurrency(monthlyIncome)}`}
            </div>
            <div className="text-sm font-medium text-muted-foreground mt-2">Income (30D)</div>
            <div className={cn(
              'text-xs font-medium mt-2',
              !hasData ? 'text-muted-foreground' : 'text-lime-dark'
            )}>
              {!hasData ? 'No forecast data' : 'Expected inflows'}
            </div>
          </div>
        </NeuroCard>

        {/* Expenses (30D) */}
        <NeuroCard className="p-6">
          <div className="text-center">
            <div className="text-4xl font-bold text-tomato">
              {!hasData ? '--' : `-${formatCompactCurrency(monthlyExpenses)}`}
            </div>
            <div className="text-sm font-medium text-muted-foreground mt-2">Expenses (30D)</div>
            <div className={cn(
              'text-xs font-medium mt-2',
              !hasData ? 'text-muted-foreground' : 'text-tomato'
            )}>
              {!hasData ? 'No forecast data' : 'Expected outflows'}
            </div>
          </div>
        </NeuroCard>
      </div>

      {/* Forecast Chart - Full Width */}
      <NeuroCard>
        <NeuroCardHeader className="pb-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              <NeuroCardTitle>{timePeriod}-Week Forecast</NeuroCardTitle>
            </div>
            <div className="flex items-center gap-3">
              {/* Time Period Selector */}
              <Select value={timePeriod} onValueChange={(v) => setTimePeriod(v as '13' | '26' | '52')}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="13">13 weeks</SelectItem>
                  <SelectItem value="26">26 weeks</SelectItem>
                  <SelectItem value="52">52 weeks</SelectItem>
                </SelectContent>
              </Select>

              {/* Apply Saved Scenarios Button */}
              <Dialog open={savedScenariosDialogOpen} onOpenChange={setSavedScenariosDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="bg-lime/20 border-lime hover:bg-lime/30">
                    Apply Saved Scenarios
                    {appliedScenarios.length > 0 && (
                      <Badge className="ml-2 bg-lime text-foreground">{appliedScenarios.length}</Badge>
                    )}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Saved Scenarios</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-2 mt-4">
                    {savedScenarios.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        No saved scenarios yet. Build and save a scenario to see it here.
                      </p>
                    ) : (
                      savedScenarios.map((scenario) => (
                        <div
                          key={scenario.id}
                          className={cn(
                            'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors',
                            appliedScenarios.includes(scenario.id) ? 'bg-lime/10 border-lime' : 'hover:bg-muted'
                          )}
                          onClick={() => toggleAppliedScenario(scenario.id)}
                        >
                          <div>
                            <p className="font-medium">{scenario.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {scenarioTypeConfig[scenario.scenario_type]?.label}
                            </p>
                          </div>
                          {appliedScenarios.includes(scenario.id) && <CheckCircle2 className="h-5 w-5 text-lime" />}
                        </div>
                      ))
                    )}
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </NeuroCardHeader>
        <NeuroCardContent>
          {/* Legend */}
          <div className="flex items-center justify-center gap-6 mb-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[var(--chart-1)]" />
              <span>Base Forecast</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-lime" />
              <span>Scenario Forecast</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-6 h-0.5 border-b-2 border-dashed border-tomato" />
              <span>Cash Buffer (Minimum)</span>
            </div>
          </div>

          {/* Chart */}
          <ChartContainer config={chartConfig} className="h-[400px] w-full">
            <ComposedChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
              onClick={(data) => {
                if (data?.activePayload?.[0]?.payload?.weekNumber) {
                  handleChartClick(data.activePayload[0].payload.weekNumber);
                }
              }}
            >
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="week" tickLine={false} axisLine={false} tickMargin={8} tick={{ fontSize: 12 }} />
              <YAxis
                tickFormatter={formatYAxisValue}
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 12 }}
              />
              <ChartTooltip
                cursor={{ fill: 'rgba(0,0,0,0.05)' }}
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="rounded-xl border bg-white/90 backdrop-blur-sm p-4 shadow-xl">
                        <p className="font-semibold mb-2">{label}</p>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between gap-4">
                            <span className="text-muted-foreground">Position:</span>
                            <span className="font-medium">{formatCurrency(data.base)}</span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-lime-dark">Income:</span>
                            <span className="font-medium text-lime-dark">+{formatCurrency(data.cashIn)}</span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-tomato">Expenses:</span>
                            <span className="font-medium text-tomato">-{formatCurrency(data.cashOut)}</span>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground mt-3 pt-2 border-t">Click to ask TAMI about this week</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <defs>
                <linearGradient id="fillBase" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0.1} />
                </linearGradient>
                <linearGradient id="fillScenario" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--lime)" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="var(--lime)" stopOpacity={0.1} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="base" stroke="var(--chart-1)" strokeWidth={2} fill="url(#fillBase)" fillOpacity={0.4} />
              {comparison && (
                <Area type="monotone" dataKey="scenario" stroke="var(--lime)" strokeWidth={2} fill="url(#fillScenario)" fillOpacity={0.4} />
              )}
              {bufferAmount > 0 && (
                <Line type="monotone" dataKey="buffer" stroke="#ef4444" strokeDasharray="8 4" strokeWidth={2} dot={false} activeDot={false} />
              )}
              {/* Collaborator markers on chart */}
              {MOCK_COLLABORATORS.filter(c => c.weekNumber).map((collab) => {
                const weekData = chartData.find(d => d.weekNumber === collab.weekNumber);
                if (!weekData) return null;
                return (
                  <ReferenceDot
                    key={collab.id}
                    x={weekData.week}
                    y={weekData.base}
                    r={8}
                    fill={collab.color.replace('bg-', '#')}
                    stroke="white"
                    strokeWidth={2}
                  />
                );
              })}
              {/* Highlighted week marker (from navigation) */}
              {highlightedWeek && (() => {
                const weekData = chartData.find(d => d.weekNumber === highlightedWeek);
                if (!weekData) return null;
                return (
                  <ReferenceDot
                    key="highlighted-week"
                    x={weekData.week}
                    y={weekData.base}
                    r={12}
                    fill="#ef4444"
                    stroke="white"
                    strokeWidth={3}
                    className="animate-pulse"
                  />
                );
              })()}
            </ComposedChart>
          </ChartContainer>

        </NeuroCardContent>
      </NeuroCard>

      {/* TAMI Chat Section - Inline below forecast */}
      <TAMIChatInline
        userId={user?.id || ''}
        selectedWeek={selectedWeek}
        forecastData={baseForecast}
        suggestions={allSuggestions}
        clients={clients}
      />

      {/* Suggested Scenarios Section */}
      <NeuroCard>
        <NeuroCardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <NeuroCardTitle>Suggested Scenarios</NeuroCardTitle>
            <Badge className="bg-lime/20 text-lime-dark border-lime/30">{allSuggestions.length} ready to run</Badge>
          </div>
        </NeuroCardHeader>
        <NeuroCardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {allSuggestions.slice(0, 3).map((suggestion, index) => {
              const priority = suggestion.priority || 'medium';
              const hasAlert = !!suggestion.source_alert_id;

              return (
                <div
                  key={index}
                  onClick={() => handleStartScenario(suggestion.scenario_type, suggestion)}
                  className={cn(
                    'group cursor-pointer p-5 rounded-2xl bg-white transition-all duration-300',
                    'hover:shadow-lg hover:scale-[1.02]'
                  )}
                >
                  {/* Priority Badge */}
                  <div className="mb-3">
                    <Badge
                      variant="outline"
                      className={cn(
                        'text-xs font-semibold uppercase tracking-wide',
                        priority === 'high'
                          ? 'bg-tomato/10 border-tomato/30 text-tomato'
                          : priority === 'medium'
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-600'
                            : 'bg-lime/10 border-lime/30 text-lime-dark'
                      )}
                    >
                      {priority === 'high' ? 'High Risk' : priority === 'medium' ? 'Medium Risk' : 'Low Risk'}
                    </Badge>
                  </div>

                  {/* Scenario Question */}
                  <h3 className="font-semibold text-gunmetal mb-2 group-hover:text-gunmetal/80">
                    {suggestion.name}
                  </h3>

                  {/* Buffer Impact - personalized */}
                  <p className="text-sm text-muted-foreground mb-3">
                    <span className="font-medium text-gunmetal">Buffer impact:</span> {suggestion.buffer_impact || 'Calculating...'}
                    <br />
                    <span className="text-xs">{suggestion.description}</span>
                  </p>

                  {/* Context - always show risk context for buffer protection */}
                  {hasAlert ? (
                    <Link
                      to={`/action-monitor?alert=${suggestion.source_alert_id}`}
                      className="flex items-center gap-2 text-xs text-amber-600 mb-4 p-2 rounded-lg bg-amber-50 border border-amber-100 hover:bg-amber-100 transition-colors"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                      <span className="flex-1">Linked to active alert</span>
                      <span className="text-coral flex items-center gap-1">
                        View <ExternalLink className="w-3 h-3" />
                      </span>
                    </Link>
                  ) : (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-4 p-2 rounded-lg bg-gray-50 border border-gray-100">
                      <TrendingDown className="w-3.5 h-3.5 flex-shrink-0" />
                      <span>{suggestion.risk_context || 'Test your buffer resilience'}</span>
                    </div>
                  )}

                  {/* Run Button */}
                  <Button className="w-full bg-coral hover:bg-coral/90 text-white">
                    Run Scenario
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              );
            })}
          </div>
        </NeuroCardContent>
      </NeuroCard>

      {/* Test Your Own Scenario Section */}
      <NeuroCard>
        <NeuroCardHeader className="pb-4">
          <NeuroCardTitle>Test Your Own Scenario</NeuroCardTitle>
        </NeuroCardHeader>
        <NeuroCardContent>
              {/* Scenario Result Summary */}
              {comparison && (
                <div className="mb-6 p-4 bg-gunmetal/5 rounded-lg border border-gunmetal/10">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Overall Scenario Impact</p>
                      <h3 className="font-semibold text-lg">{scenarioName}</h3>
                    </div>
                    <Badge variant={riskLevel === 'Low' ? 'default' : 'destructive'} className="text-sm px-3 py-1">
                      {riskLevel === 'Low' ? 'Buffer Safe' : 'Buffer At Risk'}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Impact at Week 13</p>
                      <p
                        className={cn(
                          'text-2xl font-bold',
                          parseFloat(comparison.scenario_forecast.weeks[12]?.ending_balance || '0') -
                            parseFloat(comparison.base_forecast.weeks[12]?.ending_balance || '0') >= 0
                            ? 'text-lime'
                            : 'text-tomato'
                        )}
                      >
                        {formatCurrency(
                          parseFloat(comparison.scenario_forecast.weeks[12]?.ending_balance || '0') -
                            parseFloat(comparison.base_forecast.weeks[12]?.ending_balance || '0')
                        )}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Base Position</p>
                      <p className="text-xl font-semibold">
                        {formatCurrency(comparison.base_forecast.weeks[12]?.ending_balance || '0')}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Scenario Position</p>
                      <p className="text-xl font-semibold">
                        {formatCurrency(comparison.scenario_forecast.weeks[12]?.ending_balance || '0')}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-4">
                    <Button onClick={handleSaveScenario} className="bg-lime text-foreground hover:bg-lime/90">
                      <Save className="h-4 w-4 mr-2" />
                      Save Scenario
                    </Button>
                    <Button variant="destructive" onClick={handleDiscardScenario}>
                      <X className="h-4 w-4 mr-2" />
                      Discard
                    </Button>
                  </div>
                </div>
              )}

              {/* Form */}
              {!comparison && (
                <div className="space-y-4 p-4 bg-white/60 rounded-xl border border-white/40">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="space-y-2">
                      <Label>Scenario Name</Label>
                      <Input
                        value={scenarioName}
                        onChange={(e) => setScenarioName(e.target.value)}
                        placeholder="Client Loss Scenario"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Scenario Type</Label>
                      <Select value={scenarioType} onValueChange={(v) => setScenarioType(v as ScenarioType)}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(scenarioTypeConfig).map(([type, config]) => (
                            <SelectItem key={type} value={type}>
                              {config.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label>Effective Date</Label>
                      <Input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
                    </div>

                    {/* Client selector */}
                    {['client_loss', 'client_change', 'payment_delay_in'].includes(scenarioType) && (
                      <div className="space-y-2">
                        <Label>Client Name</Label>
                        <Select value={selectedClient} onValueChange={setSelectedClient}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select client" />
                          </SelectTrigger>
                          <SelectContent>
                            {clients.map((client) => (
                              <SelectItem key={client.id} value={client.id}>
                                {client.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {/* Expense selector */}
                    {scenarioType === 'payment_delay_out' && (
                      <div className="space-y-2">
                        <Label>Expense / Vendor</Label>
                        <Select value={selectedExpense} onValueChange={setSelectedExpense}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select expense" />
                          </SelectTrigger>
                          <SelectContent>
                            {expenses.map((expense) => (
                              <SelectItem key={expense.id} value={expense.id}>
                                {expense.name} ({formatCurrency(parseFloat(expense.monthly_amount))}/mo)
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {/* Inferred amount for client_loss */}
                    {scenarioType === 'client_loss' && selectedClient && (
                      <div className="space-y-2">
                        <Label>Monthly Impact</Label>
                        <div className="h-10 px-3 py-2 border rounded-md bg-muted text-muted-foreground flex items-center">
                          {getInferredClientAmount()
                            ? formatCurrency(parseFloat(getInferredClientAmount()!))
                            : 'Select a client'}
                        </div>
                      </div>
                    )}

                    {/* Amount input */}
                    {requiresAmountInput() && (
                      <div className="space-y-2">
                        <Label>{getAmountLabel()}</Label>
                        <Input
                          type="number"
                          value={amount}
                          onChange={(e) => setAmount(e.target.value)}
                          placeholder="10000"
                        />
                      </div>
                    )}

                    {/* Delay days */}
                    {['payment_delay_in', 'payment_delay_out'].includes(scenarioType) && (
                      <div className="space-y-2">
                        <Label>Delay (days)</Label>
                        <Input
                          type="number"
                          value={delayDays}
                          onChange={(e) => setDelayDays(e.target.value)}
                          placeholder="14"
                        />
                      </div>
                    )}
                  </div>

                  {buildError && (
                    <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-sm text-destructive">
                      {buildError}
                    </div>
                  )}

                  <div className="flex gap-3">
                    <Button variant="outline" onClick={handleDiscardScenario} disabled={isBuildingScenario}>
                      Cancel
                    </Button>
                    <Button
                      onClick={handleBuildScenario}
                      disabled={isBuildingScenario || !scenarioType}
                      className="bg-primary"
                    >
                      {isBuildingScenario ? 'Building...' : 'Build Scenario'}
                    </Button>
                  </div>
                </div>
              )}
        </NeuroCardContent>
      </NeuroCard>

      {/* Floating Notification */}
      <FloatingNotification
        show={showNotification}
        onDismiss={() => setShowNotification(false)}
        onAction={() => {
          setShowNotification(false);
          // Could navigate to update or refresh data
        }}
      />
    </div>
  );
}
