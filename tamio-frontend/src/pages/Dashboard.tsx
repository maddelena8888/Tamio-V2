import { useEffect, useState, Fragment, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardHeader, NeuroCardTitle, NeuroCardContent } from '@/components/ui/neuro-card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from '@/components/ui/chart';
import { AreaChart, Area, XAxis, YAxis, ReferenceLine, CartesianGrid } from 'recharts';
import { AlertTriangle, ChevronDown, ChevronUp, Bot, User, Send, Shield, ShieldAlert, ShieldCheck, Info, Sparkles, MessageSquare } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { Progress } from '@/components/ui/progress';
import { getForecast } from '@/lib/api/forecast';
import { getCashPosition, getClients } from '@/lib/api/data';
import { getScenarioSuggestions, getRules } from '@/lib/api/scenarios';
import { sendChatMessageStreaming, formatConversationHistory } from '@/lib/api/tami';
import type { ForecastResponse, CashPositionResponse, ScenarioSuggestion, FinancialRule, Client, ChatMode, SuggestedAction } from '@/lib/api/types';
import ReactMarkdown from 'react-markdown';

const chartConfig = {
  endingBalance: {
    label: 'Ending Balance',
    color: 'var(--chart-1)',
  },
  cashBuffer: {
    label: 'Cash Buffer (Minimum)',
    color: 'var(--chart-3)',
  },
} satisfies ChartConfig;

interface TamiMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  mode?: ChatMode;
  suggestedActions?: SuggestedAction[];
  isStreaming?: boolean;
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [cashPosition, setCashPosition] = useState<CashPositionResponse | null>(null);
  const [suggestions, setSuggestions] = useState<ScenarioSuggestion[]>([]);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedWeeks, setExpandedWeeks] = useState<Record<number, boolean>>({});

  // TAMI chatbot state
  const [isTamiOpen, setIsTamiOpen] = useState(false);
  const [tamiMessages, setTamiMessages] = useState<TamiMessage[]>([]);
  const [tamiInput, setTamiInput] = useState('');
  const [isTamiLoading, setIsTamiLoading] = useState(false);
  const tamiScrollRef = useRef<HTMLDivElement>(null);
  const tamiInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const [forecastData, cashData, suggestionsData, rulesData, clientsData] = await Promise.all([
          getForecast(user.id),
          getCashPosition(user.id),
          getScenarioSuggestions(user.id).catch(() => ({ suggestions: [] })),
          getRules(user.id).catch(() => []),
          getClients(user.id).catch(() => []),
        ]);

        setForecast(forecastData);
        setCashPosition(cashData);
        setSuggestions(suggestionsData.suggestions || []);
        setRules(rulesData);
        setClients(clientsData);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user]);

  // Auto-scroll TAMI chat when new messages arrive
  useEffect(() => {
    if (tamiScrollRef.current) {
      tamiScrollRef.current.scrollTop = tamiScrollRef.current.scrollHeight;
    }
  }, [tamiMessages]);

  // Calculate KPIs
  const totalIncome30D = forecast?.weeks.slice(0, 4).reduce(
    (sum, week) => sum + parseFloat(week.cash_in || '0'),
    0
  ) || 0;

  const totalExpenses30D = forecast?.weeks.slice(0, 4).reduce(
    (sum, week) => sum + parseFloat(week.cash_out || '0'),
    0
  ) || 0;

  const availableCash = parseFloat(cashPosition?.total_starting_cash || '0');

  // Get buffer rule threshold
  const bufferRule = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
  const bufferMonths = (bufferRule?.threshold_config as { months?: number })?.months || 3;
  const monthlyExpenses = totalExpenses30D;
  const bufferAmount = monthlyExpenses * bufferMonths;

  // Determine buffer status
  const lowestBalance = forecast?.summary.lowest_cash_amount
    ? parseFloat(forecast.summary.lowest_cash_amount)
    : availableCash;
  const isAtRisk = lowestBalance > 0 && lowestBalance < bufferAmount;
  const isBreach = lowestBalance <= 0;

  // Chart data
  const chartData = forecast?.weeks.map((week) => ({
    week: `Week ${week.week_number}`,
    endingBalance: parseFloat(week.ending_balance),
    cashIn: parseFloat(week.cash_in),
    cashOut: parseFloat(week.cash_out),
    cashBuffer: bufferAmount,
  })) || [];

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const toggleWeek = (weekNumber: number) => {
    setExpandedWeeks((prev) => ({
      ...prev,
      [weekNumber]: !prev[weekNumber],
    }));
  };

  // TAMI chatbot handlers
  const handleTamiSend = async (messageText?: string) => {
    const text = messageText || tamiInput.trim();
    if (!text || !user) return;

    const userMessage: TamiMessage = {
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setTamiMessages((prev) => [...prev, userMessage]);
    setTamiInput('');
    setIsTamiLoading(true);

    // Add streaming placeholder message
    const streamingMessage: TamiMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setTamiMessages((prev) => [...prev, streamingMessage]);

    const conversationHistory = formatConversationHistory(
      tamiMessages.map((m) => ({
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
        active_scenario_id: null,
      },
      // onChunk
      (chunk) => {
        setTamiMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, content: lastMsg.content + chunk }
            ];
          }
          return prev;
        });
      },
      // onDone
      (event) => {
        setTamiMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              {
                ...lastMsg,
                isStreaming: false,
                mode: event.mode,
                suggestedActions: event.ui_hints?.suggested_actions,
              }
            ];
          }
          return prev;
        });
        setIsTamiLoading(false);
        tamiInputRef.current?.focus();
      },
      // onError
      (error) => {
        console.error('Streaming error:', error);
        setTamiMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg?.role === 'assistant' && lastMsg.isStreaming) {
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
        setIsTamiLoading(false);
        tamiInputRef.current?.focus();
      }
    );
  };

  const handleTamiKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTamiSend();
    }
  };

  // Generate suggested scenarios based on client concentration risks
  const generateSuggestedScenarios = (): ScenarioSuggestion[] => {
    const generatedSuggestions: ScenarioSuggestion[] = [];

    // Calculate total income from clients
    const totalClientIncome = clients.reduce((sum, client) => {
      const amount = parseFloat(client.billing_config?.amount || '0');
      return sum + amount;
    }, 0);

    // Check for high concentration clients (>40%)
    clients.forEach((client) => {
      const clientAmount = parseFloat(client.billing_config?.amount || '0');
      const concentration = totalClientIncome > 0 ? (clientAmount / totalClientIncome) * 100 : 0;

      if (concentration > 40) {
        generatedSuggestions.push({
          scenario_type: 'payment_delay_in',
          name: `Late payment from ${client.name}`,
          description: `${client.name} represents ${concentration.toFixed(0)}% of your income. A late payment could significantly impact cash flow.`,
          prefill_params: { client_id: client.id, delay_days: 30 },
          priority: 'high',
        });

        generatedSuggestions.push({
          scenario_type: 'client_loss',
          name: `Lose ${client.name}`,
          description: `What happens if you lose your largest client who accounts for ${concentration.toFixed(0)}% of revenue?`,
          prefill_params: { client_id: client.id },
          priority: 'high',
        });
      } else if (concentration > 25) {
        generatedSuggestions.push({
          scenario_type: 'payment_delay_in',
          name: `Late payment from ${client.name}`,
          description: `${client.name} is ${concentration.toFixed(0)}% of income. Explore the impact of delayed payment.`,
          prefill_params: { client_id: client.id, delay_days: 14 },
          priority: 'medium',
        });
      }
    });

    // Check for clients with high churn risk
    clients.filter(c => c.churn_risk === 'high').forEach((client) => {
      if (!generatedSuggestions.find(s => s.prefill_params?.client_id === client.id && s.scenario_type === 'client_loss')) {
        generatedSuggestions.push({
          scenario_type: 'client_loss',
          name: `Lose ${client.name}`,
          description: `${client.name} has high churn risk. Plan for potential loss.`,
          prefill_params: { client_id: client.id },
          priority: 'high',
        });
      }
    });

    // Check for clients with payment delays
    clients.filter(c => c.payment_behavior === 'delayed').forEach((client) => {
      if (!generatedSuggestions.find(s => s.prefill_params?.client_id === client.id && s.scenario_type === 'payment_delay_in')) {
        generatedSuggestions.push({
          scenario_type: 'payment_delay_in',
          name: `Extended delay from ${client.name}`,
          description: `${client.name} has a history of late payments. Model an extended delay.`,
          prefill_params: { client_id: client.id, delay_days: 30 },
          priority: 'medium',
        });
      }
    });

    return generatedSuggestions.slice(0, 6); // Limit to 6 suggestions
  };

  // Combine API suggestions with generated ones
  const allSuggestions = suggestions.length > 0 ? suggestions : generateSuggestedScenarios();

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="space-y-6 min-h-screen">
      {/* Company Name Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{user?.company_name || 'Dashboard'}</h1>
        <Button
          variant="ghost"
          onClick={() => setIsTamiOpen(true)}
          className="gap-2 bg-lime text-gunmetal font-semibold shadow-md hover:bg-lime hover:text-gunmetal hover:shadow-lg hover:brightness-105 transition-all duration-200"
        >
          <Bot className="h-4 w-4" />
          Ask TAMI
        </Button>
      </div>

      {/* KPI Cards - Neumorphic Design */}
      <div className="relative grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Upcoming Income */}
        <NeuroCard>
          <div className="text-3xl font-bold text-gunmetal text-center">{formatCurrency(totalIncome30D)}</div>
          <div className="text-sm font-medium text-gunmetal/60 text-center mt-2">Total Income (30D)</div>
        </NeuroCard>

        {/* Upcoming Expenses */}
        <NeuroCard>
          <div className="text-3xl font-bold text-gunmetal text-center">{formatCurrency(totalExpenses30D)}</div>
          <div className="text-sm font-medium text-gunmetal/60 text-center mt-2">Total Expenses (30D)</div>
        </NeuroCard>

        {/* Available Cash */}
        <NeuroCard>
          <div className="text-3xl font-bold text-gunmetal text-center">{formatCurrency(availableCash)}</div>
          <div className="text-sm font-medium text-gunmetal/60 text-center mt-2">Available Cash</div>
        </NeuroCard>
      </div>

      {/* Forecast Chart */}
      <NeuroCard>
        <NeuroCardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-3">
            <NeuroCardTitle>13 Week Forecast</NeuroCardTitle>
            {/* Confidence Score Indicator */}
            {forecast?.confidence && (
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className={`h-7 gap-1.5 text-xs font-medium ${
                      forecast.confidence.overall_level === 'high'
                        ? 'border-green-500 text-green-600 hover:bg-green-50'
                        : forecast.confidence.overall_level === 'medium'
                        ? 'border-amber-500 text-amber-600 hover:bg-amber-50'
                        : 'border-red-500 text-red-600 hover:bg-red-50'
                    }`}
                  >
                    {forecast.confidence.overall_level === 'high' ? (
                      <ShieldCheck className="h-3.5 w-3.5" />
                    ) : forecast.confidence.overall_level === 'medium' ? (
                      <Shield className="h-3.5 w-3.5" />
                    ) : (
                      <ShieldAlert className="h-3.5 w-3.5" />
                    )}
                    {forecast.confidence.overall_percentage}% Confidence
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80" align="start">
                  <div className="space-y-4">
                    <div>
                      <h4 className="font-semibold text-sm mb-1">Forecast Confidence</h4>
                      <p className="text-xs text-muted-foreground">
                        Based on how well your data is backed by accounting software
                      </p>
                    </div>

                    {/* Progress bar */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs">
                        <span>Overall Score</span>
                        <span className="font-medium">{forecast.confidence.overall_percentage}%</span>
                      </div>
                      <Progress
                        value={forecast.confidence.overall_percentage}
                        className={`h-2 ${
                          forecast.confidence.overall_level === 'high'
                            ? '[&>div]:bg-green-500'
                            : forecast.confidence.overall_level === 'medium'
                            ? '[&>div]:bg-amber-500'
                            : '[&>div]:bg-red-500'
                        }`}
                      />
                    </div>

                    {/* Breakdown */}
                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between py-1.5 border-b">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-green-500" />
                          <span>High confidence</span>
                        </div>
                        <div className="text-right">
                          <span className="font-medium">{forecast.confidence.breakdown.high_confidence_count}</span>
                          <span className="text-muted-foreground ml-1">items</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between py-1.5 border-b">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-amber-500" />
                          <span>Medium confidence</span>
                        </div>
                        <div className="text-right">
                          <span className="font-medium">{forecast.confidence.breakdown.medium_confidence_count}</span>
                          <span className="text-muted-foreground ml-1">items</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-red-500" />
                          <span>Low confidence</span>
                        </div>
                        <div className="text-right">
                          <span className="font-medium">{forecast.confidence.breakdown.low_confidence_count}</span>
                          <span className="text-muted-foreground ml-1">items</span>
                        </div>
                      </div>
                    </div>

                    {/* Suggestions */}
                    {forecast.confidence.improvement_suggestions.length > 0 && (
                      <div className="pt-2 border-t">
                        <div className="flex items-center gap-1.5 mb-2">
                          <Info className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-xs font-medium">To improve confidence:</span>
                        </div>
                        <ul className="text-xs text-muted-foreground space-y-1">
                          {forecast.confidence.improvement_suggestions.slice(0, 3).map((suggestion, i) => (
                            <li key={i} className="leading-relaxed">• {suggestion}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </PopoverContent>
              </Popover>
            )}
          </div>
          <HoverCard openDelay={200} closeDelay={100}>
            <HoverCardTrigger asChild>
              <Badge
                variant={isBreach ? 'destructive' : isAtRisk ? 'secondary' : 'default'}
                className={`cursor-pointer ${
                  isBreach
                    ? 'bg-tomato text-white'
                    : isAtRisk
                    ? 'bg-mimi-pink text-foreground'
                    : 'bg-lime text-foreground'
                }`}
              >
                {isBreach ? 'Buffer Breach' : isAtRisk ? 'At Risk' : 'Cash Buffer Safe'}
              </Badge>
            </HoverCardTrigger>
            <HoverCardContent className="w-80" side="bottom" align="end" sideOffset={8}>
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  {isBreach ? (
                    <ShieldAlert className="h-5 w-5 text-tomato" />
                  ) : isAtRisk ? (
                    <Shield className="h-5 w-5 text-mimi-pink" />
                  ) : (
                    <ShieldCheck className="h-5 w-5 text-lime" />
                  )}
                  <h4 className="font-semibold">
                    {isBreach ? 'Cash Buffer Breach' : isAtRisk ? 'Cash Buffer At Risk' : 'Cash Buffer Healthy'}
                  </h4>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Required Buffer:</span>
                    <span className="font-medium">{formatCurrency(bufferAmount)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Lowest Balance:</span>
                    <span className={`font-medium ${isBreach ? 'text-tomato' : isAtRisk ? 'text-mimi-pink' : ''}`}>
                      {formatCurrency(lowestBalance)}
                    </span>
                  </div>
                  {forecast?.summary.lowest_cash_week && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Lowest Week:</span>
                      <span className="font-medium">Week {forecast.summary.lowest_cash_week}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Buffer Coverage:</span>
                    <span className="font-medium">{bufferMonths} months</span>
                  </div>
                </div>

                {(isBreach || isAtRisk) && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground">
                      {isBreach
                        ? `Your forecast shows cash dropping to ${formatCurrency(lowestBalance)}, which is below zero. Consider reducing expenses or accelerating revenue.`
                        : `Your lowest projected balance of ${formatCurrency(lowestBalance)} is below your ${formatCurrency(bufferAmount)} buffer target. Consider building more runway.`
                      }
                    </p>
                  </div>
                )}

                {!isBreach && !isAtRisk && (
                  <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground">
                      Your cash position stays above the {bufferMonths}-month buffer throughout the forecast period.
                    </p>
                  </div>
                )}
              </div>
            </HoverCardContent>
          </HoverCard>
        </NeuroCardHeader>
        <NeuroCardContent>
          {chartData.length > 0 ? (
            <ChartContainer config={chartConfig} className="h-[300px] w-full">
              <AreaChart
                data={chartData}
                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
              >
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis
                  dataKey="week"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  tick={{ fontSize: 12 }}
                  tickFormatter={(value) => value.replace('Week ', 'W')}
                />
                <YAxis
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12 }}
                />
                <ChartTooltip
                  cursor={false}
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-xl">
                          <p className="font-medium mb-2">{label}</p>
                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between gap-4">
                              <span className="text-muted-foreground">Position:</span>
                              <span className="font-medium">{formatCurrency(data.endingBalance)}</span>
                            </div>
                            <div className="flex justify-between gap-4">
                              <span className="text-lime">Income:</span>
                              <span className="font-medium text-lime">+{formatCurrency(data.cashIn)}</span>
                            </div>
                            <div className="flex justify-between gap-4">
                              <span className="text-tomato">Expenses:</span>
                              <span className="font-medium text-tomato">-{formatCurrency(data.cashOut)}</span>
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <defs>
                  <linearGradient id="fillEndingBalance" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="5%"
                      stopColor="var(--chart-1)"
                      stopOpacity={0.8}
                    />
                    <stop
                      offset="95%"
                      stopColor="var(--chart-1)"
                      stopOpacity={0.1}
                    />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="endingBalance"
                  stroke="var(--chart-1)"
                  strokeWidth={2}
                  fill="url(#fillEndingBalance)"
                  fillOpacity={0.4}
                />
                <ReferenceLine
                  y={bufferAmount}
                  stroke="var(--chart-3)"
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  label={{
                    value: 'Cash Buffer',
                    position: 'insideTopRight',
                    fill: 'var(--chart-3)',
                    fontSize: 12,
                    fontWeight: 500,
                  }}
                />
              </AreaChart>
            </ChartContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-muted-foreground">
              No forecast data available. Add clients and expenses to generate a forecast.
            </div>
          )}
          <div className="flex items-center justify-center gap-6 mt-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[var(--chart-1)]" />
              <span>Ending Balance</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-0.5 border-b-2 border-dashed border-[var(--chart-3)]" />
              <span>Cash Buffer (Minimum)</span>
            </div>
          </div>
        </NeuroCardContent>
      </NeuroCard>

      {/* Suggested Scenarios */}
      {allSuggestions.length > 0 && (
        <NeuroCard>
          <NeuroCardHeader className="pb-0">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-muted">
                <AlertTriangle className="h-5 w-5 text-foreground" />
              </div>
              <div>
                <NeuroCardTitle>Suggested Scenarios</NeuroCardTitle>
                <p className="text-sm text-muted-foreground mt-0.5">Based on your risk profile</p>
              </div>
            </div>
          </NeuroCardHeader>
          <NeuroCardContent className="pt-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {allSuggestions.slice(0, 3).map((suggestion, index) => (
                <NeuroCard
                  key={index}
                  className={`cursor-pointer p-5 hover:shadow-xl group ${
                    suggestion.priority === 'high'
                      ? 'hover:border-tomato/50'
                      : suggestion.priority === 'medium'
                      ? 'hover:border-amber-500/50'
                      : 'hover:border-primary/50'
                  }`}
                  onClick={() => navigate(`/scenarios?type=${suggestion.scenario_type}`)}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div
                      className={`p-2 rounded-lg ${
                        suggestion.priority === 'high'
                          ? 'bg-tomato/10'
                          : suggestion.priority === 'medium'
                          ? 'bg-amber-500/10'
                          : 'bg-muted'
                      }`}
                    >
                      <AlertTriangle
                        className={`h-4 w-4 ${
                          suggestion.priority === 'high'
                            ? 'text-tomato'
                            : suggestion.priority === 'medium'
                            ? 'text-amber-500'
                            : 'text-muted-foreground'
                        }`}
                      />
                    </div>
                    <Badge
                      className={`text-xs font-medium ${
                        suggestion.priority === 'high'
                          ? 'bg-tomato/10 text-tomato border-tomato/20 hover:bg-tomato/10'
                          : suggestion.priority === 'medium'
                          ? 'bg-amber-500/10 text-amber-600 border-amber-500/20 hover:bg-amber-500/10'
                          : 'bg-muted text-muted-foreground'
                      }`}
                      variant="outline"
                    >
                      {suggestion.priority}
                    </Badge>
                  </div>
                  <h4 className="font-semibold text-base mb-2 group-hover:text-primary transition-colors">
                    {suggestion.name}
                  </h4>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {suggestion.description}
                  </p>
                </NeuroCard>
              ))}
            </div>
          </NeuroCardContent>
        </NeuroCard>
      )}

      {/* Weekly Breakdown Table */}
      <NeuroCard>
        <NeuroCardHeader>
          <NeuroCardTitle>Weekly Breakdown</NeuroCardTitle>
        </NeuroCardHeader>
        <NeuroCardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Week</TableHead>
                <TableHead className="text-right">Starting</TableHead>
                <TableHead className="text-right text-lime">Income</TableHead>
                <TableHead className="text-right text-tomato">Costs</TableHead>
                <TableHead className="text-right">Ending</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {forecast?.weeks.map((week) => (
                <Fragment key={week.week_number}>
                  <TableRow
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => toggleWeek(week.week_number)}
                  >
                    <TableCell className="font-medium">
                      {`Week ${week.week_number}`}
                      <div className="text-xs text-muted-foreground">
                        {new Date(week.week_start).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(parseFloat(week.starting_balance))}
                    </TableCell>
                    <TableCell className="text-right text-lime">
                      +{formatCurrency(parseFloat(week.cash_in))}
                    </TableCell>
                    <TableCell className="text-right text-tomato">
                      -{formatCurrency(parseFloat(week.cash_out))}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(parseFloat(week.ending_balance))}
                    </TableCell>
                    <TableCell>
                      {expandedWeeks[week.week_number] ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </TableCell>
                  </TableRow>
                  {expandedWeeks[week.week_number] && week.events.length > 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="bg-muted/30 p-4">
                        <div className="space-y-2">
                          {week.events.map((event) => (
                            <div
                              key={event.id}
                              className="flex items-center justify-between text-sm"
                            >
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className={
                                    event.direction === 'in'
                                      ? 'border-lime/50 text-lime'
                                      : 'border-tomato/50 text-tomato'
                                  }
                                >
                                  {event.direction === 'in' ? 'IN' : 'OUT'}
                                </Badge>
                                <span>{event.category}</span>
                                {event.confidence !== 'high' && (
                                  <Badge variant="secondary" className="text-xs">
                                    {event.confidence}
                                  </Badge>
                                )}
                              </div>
                              <span
                                className={
                                  event.direction === 'in' ? 'text-lime' : 'text-tomato'
                                }
                              >
                                {event.direction === 'in' ? '+' : '-'}
                                {formatCurrency(parseFloat(event.amount))}
                              </span>
                            </div>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </NeuroCardContent>
      </NeuroCard>

      {/* TAMI Chatbot Sheet */}
      <Sheet open={isTamiOpen} onOpenChange={setIsTamiOpen}>
        <SheetContent className="w-[400px] sm:w-[540px] flex flex-col p-0">
          <SheetHeader className="p-4 border-b bg-card">
            <SheetTitle className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-lime">
                <Bot className="h-5 w-5 text-gunmetal" />
              </div>
              <div>
                <span className="block">Ask TAMI</span>
                <span className="text-xs font-normal text-muted-foreground">Your AI financial assistant</span>
              </div>
            </SheetTitle>
          </SheetHeader>

          {/* Chat Messages */}
          <ScrollArea className="flex-1 p-4" ref={tamiScrollRef}>
            {tamiMessages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-8">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-lime to-lime/60 flex items-center justify-center mb-4 shadow-md">
                  <Bot className="h-6 w-6 text-gunmetal" />
                </div>
                <h3 className="font-semibold mb-1">How can I help?</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Ask about your forecast, run scenarios, or plan goals.
                </p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {[
                    { text: "What's my runway?", icon: Sparkles },
                    { text: "What if I lose a client?", icon: AlertTriangle },
                    { text: "Improve cash flow?", icon: MessageSquare },
                  ].map((prompt, index) => {
                    const Icon = prompt.icon;
                    return (
                      <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        className="h-8 px-3 gap-1.5 text-xs hover:border-lime hover:bg-lime/10 transition-all"
                        onClick={() => handleTamiSend(prompt.text)}
                      >
                        <Icon className="h-3 w-3 text-muted-foreground" />
                        {prompt.text}
                      </Button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {tamiMessages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex gap-2 ${
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    {message.role === 'assistant' && (
                      <Avatar className="h-7 w-7 border border-lime/30">
                        <AvatarFallback className="bg-primary text-primary-foreground">
                          <Bot className="h-3.5 w-3.5" />
                        </AvatarFallback>
                      </Avatar>
                    )}
                    <div
                      className={`max-w-[85%] ${
                        message.role === 'user'
                          ? 'bg-primary text-primary-foreground rounded-2xl rounded-br-md px-3 py-2 text-sm shadow-sm'
                          : 'space-y-2'
                      }`}
                    >
                      {message.role === 'assistant' ? (
                        message.isStreaming && message.content === '' ? (
                          <div className="flex items-center gap-1 py-1">
                            <span className="w-1.5 h-1.5 bg-lime rounded-full animate-bounce [animation-delay:-0.3s]" />
                            <span className="w-1.5 h-1.5 bg-lime rounded-full animate-bounce [animation-delay:-0.15s]" />
                            <span className="w-1.5 h-1.5 bg-lime rounded-full animate-bounce" />
                          </div>
                        ) : (
                          <div className="prose prose-sm dark:prose-invert max-w-none text-sm prose-p:leading-relaxed prose-p:my-1">
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          </div>
                        )
                      ) : (
                        <p className="leading-relaxed">{message.content}</p>
                      )}

                      {message.role === 'assistant' &&
                        !message.isStreaming &&
                        message.suggestedActions &&
                        message.suggestedActions.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-3 pt-2 border-t border-border/50">
                            {message.suggestedActions.map((action, actionIndex) => (
                              <Button
                                key={actionIndex}
                                variant={action.action === 'none' ? 'outline' : 'default'}
                                size="sm"
                                className="text-xs h-7"
                                onClick={() => {
                                  if (action.action === 'none') return;
                                  if (action.action === 'call_tool') {
                                    if (action.tool_name && action.tool_args && Object.keys(action.tool_args).length > 0) {
                                      handleTamiSend(`[Action: ${action.label}] Please execute: ${action.tool_name} with parameters: ${JSON.stringify(action.tool_args)}`);
                                    } else {
                                      handleTamiSend(action.label);
                                    }
                                  }
                                }}
                              >
                                {action.label}
                              </Button>
                            ))}
                          </div>
                        )}
                    </div>
                    {message.role === 'user' && (
                      <Avatar className="h-7 w-7 border border-muted">
                        <AvatarFallback className="bg-muted">
                          <User className="h-3.5 w-3.5" />
                        </AvatarFallback>
                      </Avatar>
                    )}
                  </div>
                ))}

              </div>
            )}
          </ScrollArea>

          {/* Input Area */}
          <div className="p-3 border-t bg-card/50">
            <div className="flex gap-2 items-center">
              <Input
                ref={tamiInputRef}
                value={tamiInput}
                onChange={(e) => setTamiInput(e.target.value)}
                onKeyDown={handleTamiKeyDown}
                placeholder="Ask anything..."
                disabled={isTamiLoading}
                className="flex-1 text-sm h-10 rounded-xl bg-background border-muted-foreground/20 focus:border-lime"
              />
              <Button
                size="icon"
                onClick={() => handleTamiSend()}
                disabled={!tamiInput.trim() || isTamiLoading}
                className="h-10 w-10 rounded-xl"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
