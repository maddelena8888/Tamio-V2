import { useEffect, useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { NeuroCard, NeuroCardContent, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from '@/components/ui/chart';
import { ComposedChart, Area, XAxis, YAxis, CartesianGrid, Line } from 'recharts';
import { TrendingUp, Info } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { ScenarioBar, TransactionTable } from '@/components/forecast';
import { getForecast, getTransactions, createCustomScenario } from '@/lib/api/forecast';
import { getRules } from '@/lib/api/scenarios';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import type {
  ForecastResponse,
  TransactionItem,
  FinancialRule,
  ScenarioType,
} from '@/lib/api/types';

// ============================================================================
// Configuration
// ============================================================================

const chartConfig = {
  base: { label: 'Base Forecast', color: 'var(--chart-1)' },
  scenario: { label: 'Scenario Forecast', color: 'var(--lime)' },
  buffer: { label: 'Cash Buffer', color: 'var(--tomato)' },
} satisfies ChartConfig;

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

const formatYAxisValue = (value: number): string => {
  const absValue = Math.abs(value);
  if (absValue >= 1000000) {
    const millions = value / 1000000;
    return `$${millions.toFixed(1).replace(/\.0$/, '')}M`;
  }
  if (absValue >= 1000) {
    return `$${Math.round(value / 1000)}K`;
  }
  return `$${Math.round(value)}`;
};

// ============================================================================
// Main Component
// ============================================================================

export default function Forecast() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Data state
  const [baseForecast, setBaseForecast] = useState<ForecastResponse | null>(null);
  const [inflows, setInflows] = useState<TransactionItem[]>([]);
  const [outflows, setOutflows] = useState<TransactionItem[]>([]);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Scenario state
  const [excludedTransactions, setExcludedTransactions] = useState<Set<string>>(new Set());
  const [_customScenarioId, setCustomScenarioId] = useState<string | null>(null);

  // URL-based scenario (from ScenarioBuilder)
  const urlScenario = useMemo(() => {
    const scenarioType = searchParams.get('scenarioType');
    const name = searchParams.get('name');

    if (!scenarioType) return null;

    // Extract all scenario-specific parameters
    const params: Record<string, string> = {};
    for (const [key, value] of searchParams.entries()) {
      params[key] = value;
    }

    // Build impact statement based on scenario type
    let impact = '';
    switch (scenarioType) {
      case 'payment_delay_in':
        impact = `Simulating ${params.days || 30}-day payment delay`;
        break;
      case 'hiring':
        impact = `Adding $${Math.round(parseInt(params.salary || '0', 10) / 12).toLocaleString()}/mo payroll`;
        break;
      case 'increased_expense':
        impact = `${params.percentage || 0}% expense increase`;
        break;
      case 'client_loss':
        impact = `Removing client revenue stream`;
        break;
      case 'payment_delay_out':
        impact = `Delaying outgoing payment by ${params.days || 30} days`;
        break;
      default:
        impact = 'Custom scenario';
    }

    return {
      active: true,
      name: name || 'Custom Scenario',
      impact,
      type: scenarioType,
      params,
    };
  }, [searchParams]);

  // UI state
  const [timeRange, setTimeRange] = useState<'13w' | '26w' | '52w'>('13w');

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'forecast',
    pageData: {
      timeRange,
      activeScenario: urlScenario
        ? { id: 'url-scenario', name: urlScenario.name }
        : undefined,
      excludedTransactionsCount: excludedTransactions.size,
      runwayWeeks: baseForecast?.summary?.runway_weeks,
    },
  });

  // Parse weeks from time range
  const weeks = useMemo(() => {
    const map = { '13w': 13, '26w': 26, '52w': 52 };
    return map[timeRange];
  }, [timeRange]);

  // Fetch initial data
  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [forecastData, inflowsData, outflowsData, rulesData] = await Promise.all([
          getForecast(user.id, weeks).catch(() => null),
          getTransactions(user.id, 'inflows', timeRange).catch(() => ({ transactions: [] })),
          getTransactions(user.id, 'outflows', timeRange).catch(() => ({ transactions: [] })),
          getRules(user.id).catch(() => []),
        ]);

        setBaseForecast(forecastData);
        setInflows(inflowsData.transactions || []);
        setOutflows(outflowsData.transactions || []);
        setRules(rulesData);
      } catch (error) {
        console.error('Failed to fetch forecast data:', error);
        toast.error('Failed to load forecast data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user, weeks, timeRange]);

  // Handle toggle
  const handleToggle = useCallback(async (transactionId: string, enabled: boolean) => {
    // Update local state
    const newExcluded = new Set(excludedTransactions);
    if (enabled) {
      newExcluded.delete(transactionId);
    } else {
      newExcluded.add(transactionId);
    }
    setExcludedTransactions(newExcluded);

    // Update transaction lists
    setInflows(prev => prev.map(t =>
      t.id === transactionId ? { ...t, included: enabled } : t
    ));
    setOutflows(prev => prev.map(t =>
      t.id === transactionId ? { ...t, included: enabled } : t
    ));

    // Create/update custom scenario if there are exclusions
    if (newExcluded.size > 0 && user) {
      try {
        const response = await createCustomScenario({
          user_id: user.id,
          name: 'Custom adjustments',
          excluded_transactions: Array.from(newExcluded),
          effective_date: new Date().toISOString().split('T')[0],
        });
        setCustomScenarioId(response.scenario_id);

        toast.success('Scenario updated', {
          description: `${newExcluded.size} transaction${newExcluded.size > 1 ? 's' : ''} excluded from forecast`,
          duration: 2000,
        });
      } catch (error) {
        console.error('Failed to create custom scenario:', error);
      }
    } else if (newExcluded.size === 0) {
      // Clear scenario
      setCustomScenarioId(null);
    }
  }, [excludedTransactions, user, timeRange]);

  // Handle clear scenario
  const handleClearScenario = useCallback(() => {
    setExcludedTransactions(new Set());
    setCustomScenarioId(null);

    // Reset all transactions to included
    setInflows(prev => prev.map(t => ({ ...t, included: true })));
    setOutflows(prev => prev.map(t => ({ ...t, included: true })));

    toast.success('Scenario cleared');
  }, []);

  // Handle time range change
  const handleTimeRangeChange = useCallback((newRange: '13w' | '26w' | '52w') => {
    setTimeRange(newRange);
    // Clear scenario when changing time range
    handleClearScenario();
  }, [handleClearScenario]);

  // Handle scenario parameter change (updates URL and recalculates)
  const handleScenarioParamChange = useCallback((key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set(key, value);

    // Update the scenario name based on new params
    const scenarioType = newParams.get('scenarioType');
    if (scenarioType === 'payment_delay_in') {
      const client = key === 'client' ? value : newParams.get('client') || '';
      const days = key === 'days' ? value : newParams.get('days') || '30';
      const clientLabel: Record<string, string> = {
        'retailco-rebrand': 'RetailCo Rebrand',
        'techcorp': 'TechCorp',
        'healthtech': 'HealthTech Campaign',
      };
      newParams.set('name', `${clientLabel[client] || client} pays ${days} days late`);
    } else if (scenarioType === 'hiring') {
      const role = key === 'role' ? value : newParams.get('role') || '';
      const roleLabel: Record<string, string> = {
        'product-designer': 'Product Designer',
        'senior-developer': 'Senior Developer',
        'sales-rep': 'Sales Rep',
      };
      newParams.set('name', `Hire ${roleLabel[role] || role}`);
    } else if (scenarioType === 'increased_expense') {
      const expense = key === 'expense' ? value : newParams.get('expense') || '';
      const percentage = key === 'percentage' ? value : newParams.get('percentage') || '25';
      const expenseLabel: Record<string, string> = {
        'aws': 'AWS Infrastructure',
        'marketing': 'Marketing spend',
        'software': 'Software subscriptions',
      };
      newParams.set('name', `${expenseLabel[expense] || expense} increases ${percentage}%`);
    } else if (scenarioType === 'client_loss') {
      const client = key === 'client' ? value : newParams.get('client') || '';
      const clientLabel: Record<string, string> = {
        'techcorp': 'TechCorp',
        'retailco': 'RetailCo',
        'healthtech': 'HealthTech Campaign',
      };
      newParams.set('name', `Lose ${clientLabel[client] || client}`);
    } else if (scenarioType === 'payment_delay_out') {
      const vendor = key === 'vendor' ? value : newParams.get('vendor') || '';
      const days = key === 'days' ? value : newParams.get('days') || '30';
      const vendorLabel: Record<string, string> = {
        'aws': 'AWS',
        'figma': 'Figma',
        'office': 'Office lease',
      };
      newParams.set('name', `Delay ${vendorLabel[vendor] || vendor} payment by ${days} days`);
    }

    setSearchParams(newParams);
    toast.success('Scenario updated', { duration: 1500 });
  }, [searchParams, setSearchParams]);

  // Calculate metrics from forecast
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

  const cashPosition = parseFloat(baseForecast?.starting_cash || '0');

  // Check if any scenario is active (URL or transaction-based)
  const hasActiveScenario = excludedTransactions.size > 0 || !!urlScenario?.active;

  // Chart data
  const chartData = useMemo(() => {
    if (!baseForecast?.weeks) return [];

    return baseForecast.weeks.map((week, index) => {
      // Calculate scenario balance by excluding transactions
      let scenarioBalance = parseFloat(week.ending_balance);

      // Simple delta calculation: subtract excluded inflows, add excluded outflows
      // This is a simplified client-side calculation
      // In production, this would come from the backend scenario forecast
      if (excludedTransactions.size > 0) {
        inflows.forEach((t) => {
          if (excludedTransactions.has(t.id)) {
            // Check if this transaction falls in this week
            const txDate = new Date(t.date);
            const weekStart = new Date(week.week_start);
            const weekEnd = new Date(week.week_end);
            if (txDate >= weekStart && txDate <= weekEnd) {
              scenarioBalance -= t.amount; // Remove excluded inflow
            }
          }
        });
        outflows.forEach((t) => {
          if (excludedTransactions.has(t.id)) {
            const txDate = new Date(t.date);
            const weekStart = new Date(week.week_start);
            const weekEnd = new Date(week.week_end);
            if (txDate >= weekStart && txDate <= weekEnd) {
              scenarioBalance += t.amount; // Add back excluded outflow
            }
          }
        });
      }

      // If URL scenario is active, simulate the impact based on type
      // This is a client-side simulation - in production, backend would calculate precise impact
      if (urlScenario?.active && urlScenario.type && urlScenario.params) {
        const { type, params } = urlScenario;

        switch (type) {
          case 'payment_delay_in': {
            const delayDays = parseInt(params.days || '30', 10);
            const delayWeeks = Math.ceil(delayDays / 7);
            if (index < delayWeeks) {
              // During delay period, cash is reduced by expected client payment
              const weeklyImpact = parseFloat(week.cash_in) * 0.3;
              scenarioBalance = parseFloat(week.ending_balance) - weeklyImpact;
            }
            break;
          }

          case 'hiring': {
            const monthlyCost = parseInt(params.salary || '0', 10) / 12;
            const startDate = params.date ? new Date(params.date) : new Date();
            const weekStart = new Date(week.week_start);
            if (weekStart >= startDate) {
              // After start date, subtract weekly portion of monthly cost
              scenarioBalance = parseFloat(week.ending_balance) - (monthlyCost / 4);
            }
            break;
          }

          case 'increased_expense': {
            const percentIncrease = parseInt(params.percentage || '0', 10) / 100;
            // Estimate expense portion of cash_out (assume ~60% is variable)
            const variableExpenses = parseFloat(week.cash_out) * 0.6;
            const expenseIncrease = variableExpenses * percentIncrease;
            scenarioBalance = parseFloat(week.ending_balance) - expenseIncrease;
            break;
          }

          case 'client_loss': {
            // Assume client represents ~25% of income (conservative estimate)
            const clientIncome = parseFloat(week.cash_in) * 0.25;
            scenarioBalance = parseFloat(week.ending_balance) - clientIncome;
            break;
          }

          case 'payment_delay_out': {
            const delayDays = parseInt(params.days || '30', 10);
            const delayWeeks = Math.ceil(delayDays / 7);
            if (index < delayWeeks) {
              // During delay, we keep cash longer (positive impact)
              const weeklyBenefit = parseFloat(week.cash_out) * 0.2;
              scenarioBalance = parseFloat(week.ending_balance) + weeklyBenefit;
            }
            break;
          }
        }
      }

      return {
        week: `Week ${week.week_number}`,
        weekNumber: week.week_number,
        base: parseFloat(week.ending_balance),
        scenario: hasActiveScenario ? scenarioBalance : null,
        buffer: bufferAmount,
        cashIn: parseFloat(week.cash_in),
        cashOut: parseFloat(week.cash_out),
      };
    });
  }, [baseForecast, excludedTransactions, inflows, outflows, bufferAmount, urlScenario, hasActiveScenario]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-36 w-full rounded-2xl" />
        <div className="grid grid-cols-3 gap-5">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-[400px]" />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton className="h-[300px]" />
          <Skeleton className="h-[300px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Scenario Bar */}
      <ScenarioBar
        scenarioActive={excludedTransactions.size > 0 || !!urlScenario?.active}
        scenarioName={urlScenario?.name || (excludedTransactions.size > 0 ? 'Custom adjustments' : null)}
        impactStatement={urlScenario?.impact || (excludedTransactions.size > 0
          ? `${excludedTransactions.size} transaction${excludedTransactions.size > 1 ? 's' : ''} excluded`
          : null
        )}
        scenarioType={urlScenario?.type as ScenarioType | undefined}
        scenarioParams={urlScenario?.params}
        onParamChange={handleScenarioParamChange}
        onClearScenario={() => {
          // Clear URL params and local state
          setSearchParams({});
          handleClearScenario();
        }}
        onShare={() => toast.info('Share functionality coming soon')}
        onSecondOrderEffects={() => toast.info('Second order effects coming soon')}
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Current Position */}
        <NeuroCard className="p-6">
          <div className="text-center">
            <div className="text-4xl font-bold text-gunmetal">
              {formatCompactCurrency(cashPosition)}
            </div>
            <div className="text-sm font-medium text-muted-foreground mt-2">Current Position</div>
            <div className="flex items-center justify-center gap-1 mt-2">
              <TrendingUp className="h-3.5 w-3.5 text-lime-dark" />
              <span className="text-xs font-medium text-lime-dark">+5.9% (30D)</span>
            </div>
          </div>
        </NeuroCard>

        {/* Runway */}
        <NeuroCard className="p-6">
          <div className="text-center">
            <div className={cn(
              'text-4xl font-bold',
              !hasData ? 'text-gunmetal' :
                (baseForecast?.summary?.runway_weeks || 0) >= 12 ? 'text-lime-dark' :
                (baseForecast?.summary?.runway_weeks || 0) >= 6 ? 'text-amber-500' : 'text-tomato'
            )}>
              {!hasData ? '--' : `${baseForecast?.summary?.runway_weeks || 0}w`}
            </div>
            <div className="text-sm font-medium text-muted-foreground mt-2">Runway</div>
            <div className={cn(
              'text-xs font-medium mt-2',
              !hasData ? 'text-muted-foreground' :
                (baseForecast?.summary?.runway_weeks || 0) >= 12 ? 'text-lime-dark' :
                (baseForecast?.summary?.runway_weeks || 0) >= 6 ? 'text-amber-500' : 'text-tomato'
            )}>
              {!hasData ? 'No forecast data' :
                (baseForecast?.summary?.runway_weeks || 0) >= 12 ? 'Healthy runway' :
                (baseForecast?.summary?.runway_weeks || 0) >= 6 ? 'Monitor closely' : 'Critical'}
            </div>
          </div>
        </NeuroCard>

        {/* Buffer Status */}
        <NeuroCard className="p-6">
          <div className="text-center">
            {(() => {
              // Derive months covered from runway weeks (consistent with runway calculation)
              const runwayWeeks = baseForecast?.summary?.runway_weeks || 0;
              const monthsCovered = runwayWeeks / 4.33; // Convert weeks to months
              const isSafe = monthsCovered >= 3;
              const isCritical = monthsCovered >= 1 && monthsCovered < 3;
              // Risk = monthsCovered < 1

              const statusLabel = isSafe ? 'Safe' : isCritical ? 'Critical' : 'At Risk';
              const statusColor = isSafe ? 'text-lime-dark' : isCritical ? 'text-amber-500' : 'text-tomato';

              return (
                <>
                  <div className={cn(
                    'text-4xl font-bold',
                    !hasData ? 'text-gunmetal' : statusColor
                  )}>
                    {!hasData ? '--' : statusLabel}
                  </div>
                  <div className="flex items-center justify-center gap-1.5 mt-2">
                    <span className="text-sm font-medium text-muted-foreground">Buffer Status</span>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-[240px] text-left">
                        <p className="font-medium mb-1">Fixed obligations coverage:</p>
                        <p><span className="text-lime-400">Safe</span> = 3+ months covered</p>
                        <p><span className="text-amber-400">Critical</span> = 1-3 months covered</p>
                        <p><span className="text-red-400">At Risk</span> = less than 1 month</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <div className={cn(
                    'text-xs font-medium mt-2',
                    !hasData ? 'text-muted-foreground' : statusColor
                  )}>
                    {!hasData ? 'No forecast data' : `${monthsCovered.toFixed(1).replace(/\.0$/, '')}mo of obligations`}
                  </div>
                </>
              );
            })()}
          </div>
        </NeuroCard>
      </div>

      {/* Forecast Chart */}
      <NeuroCard>
        <NeuroCardHeader className="pb-4 flex flex-row items-center justify-between">
          <NeuroCardTitle>Forecast</NeuroCardTitle>
          <Select value={timeRange} onValueChange={handleTimeRangeChange}>
            <SelectTrigger className="w-[120px] bg-white/80">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="13w">13 weeks</SelectItem>
              <SelectItem value="26w">26 weeks</SelectItem>
              <SelectItem value="52w">52 weeks</SelectItem>
            </SelectContent>
          </Select>
        </NeuroCardHeader>
        <NeuroCardContent>
          {/* Legend */}
          <div className="flex items-center justify-center gap-6 mb-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[var(--chart-1)]" />
              <span>Base Forecast</span>
            </div>
            {hasActiveScenario && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-lime" />
                <span>Scenario Forecast</span>
              </div>
            )}
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
            >
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="week"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
                tick={{ fontSize: 12 }}
              />
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
                          {data.scenario !== null && (
                            <div className="flex justify-between gap-4">
                              <span className="text-lime-dark">Scenario:</span>
                              <span className="font-medium text-lime-dark">
                                {formatCurrency(data.scenario)}
                              </span>
                            </div>
                          )}
                          <div className="flex justify-between gap-4">
                            <span className="text-lime-dark">Income:</span>
                            <span className="font-medium text-lime-dark">
                              +{formatCurrency(data.cashIn)}
                            </span>
                          </div>
                          <div className="flex justify-between gap-4">
                            <span className="text-tomato">Expenses:</span>
                            <span className="font-medium text-tomato">
                              -{formatCurrency(data.cashOut)}
                            </span>
                          </div>
                        </div>
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
              <Area
                type="monotone"
                dataKey="base"
                stroke="var(--chart-1)"
                strokeWidth={2}
                fill="url(#fillBase)"
                fillOpacity={hasActiveScenario ? 0.2 : 0.4}
              />
              {hasActiveScenario && (
                <Area
                  type="monotone"
                  dataKey="scenario"
                  stroke="var(--lime)"
                  strokeWidth={3}
                  fill="url(#fillScenario)"
                  fillOpacity={0.4}
                />
              )}
              {bufferAmount > 0 && (
                <Line
                  type="monotone"
                  dataKey="buffer"
                  stroke="var(--tomato)"
                  strokeDasharray="8 4"
                  strokeWidth={2}
                  dot={false}
                  activeDot={false}
                />
              )}
            </ComposedChart>
          </ChartContainer>
        </NeuroCardContent>
      </NeuroCard>

      {/* Transaction Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TransactionTable
          title="Inflows"
          type="inflows"
          transactions={inflows}
          onToggle={handleToggle}
        />
        <TransactionTable
          title="Outflows"
          type="outflows"
          transactions={outflows}
          onToggle={handleToggle}
        />
      </div>
    </div>
  );
}
