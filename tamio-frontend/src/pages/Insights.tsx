import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import {
  ChartContainer,
  ChartStyle,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  PieChart,
  Pie,
  Sector,
  Label,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  LineChart,
  Line,
  ReferenceLine,
  AreaChart,
  Area,
  ReferenceArea,
} from 'recharts';
import { Link } from 'react-router-dom';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { TrendingUp, TrendingDown, Minus, Calendar, Info } from 'lucide-react';
import { getInsights } from '@/lib/api/insights';
import type { InsightsResponse } from '@/lib/api/types';
import {
  GlassCard,
  GlassCardContent,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/ui/glass-card';

// Available months for concentration view
const CONCENTRATION_MONTHS = [
  { key: 'current', label: 'Current (90 days)' },
  { key: 'oct', label: 'October 2024' },
  { key: 'nov', label: 'November 2024' },
  { key: 'dec', label: 'December 2024' },
];

export default function Insights() {
  const { user } = useAuth();
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState(CONCENTRATION_MONTHS[0].key);

  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const data = await getInsights(user.id);
        setInsights(data);
      } catch (error) {
        console.error('Failed to fetch insights:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user]);

  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
  };

  if (isLoading) {
    return (
      <div className="space-y-6 p-6 min-h-screen">
        <Skeleton className="h-10 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-64 lg:col-span-2" />
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Failed to load insights. Please try again.</p>
      </div>
    );
  }

  // ============================================================================
  // DERIVED DATA - In production, this would come from the Behavior Model Layer
  // ============================================================================

  // Brand colors for charts
  const brandColors = ['#112331', '#C5FF35', '#FFD6F0', '#FF4F3F', '#F2F8F5'];

  // Client Behavior Metrics
  const clientConcentrationData = insights.income_behaviour.revenue_concentration.map(
    (client, index) => ({
      name: client.client_name,
      value: parseFloat(client.percentage),
      cashWeighted: parseFloat(client.percentage) * 0.9, // Simulated cash-weighting
      fill: brandColors[index % brandColors.length],
    })
  );

  // Chart config for client concentration
  const clientChartConfig: ChartConfig = clientConcentrationData.reduce((acc, client, index) => {
    acc[client.name] = {
      label: client.name,
      color: brandColors[index % brandColors.length],
    };
    return acc;
  }, {} as ChartConfig);

  // Payment Reliability - enhanced with variance and trend
  const paymentReliabilityData = insights.income_behaviour.payment_behaviour.map((client) => ({
    ...client,
    mean_days: client.payment_behavior === 'on_time' ? 5 : client.payment_behavior === 'delayed' ? 18 : 10,
    variance: client.payment_behavior === 'delayed' ? 8 : 3,
    trend: client.payment_behavior === 'delayed' ? 'worsening' : 'stable',
  }));

  // Revenue at Risk - 30/60 day probability-weighted
  const revenueAtRisk30 = Math.round(
    parseFloat(insights.income_behaviour.total_monthly_revenue) *
    (parseFloat(insights.income_behaviour.revenue_at_risk_percentage) / 100) * 0.6
  );
  const revenueAtRisk60 = Math.round(
    parseFloat(insights.income_behaviour.total_monthly_revenue) *
    (parseFloat(insights.income_behaviour.revenue_at_risk_percentage) / 100)
  );

  // Expense Behavior Metrics
  const expenseVolatilityData = [
    { category: 'Payroll', volatility: 5, drift: 2, amount: 25000 },
    { category: 'Contractors', volatility: 35, drift: 12, amount: 8000 },
    { category: 'Marketing', volatility: 45, drift: -5, amount: 3500 },
    { category: 'Utilities', volatility: 8, drift: 3, amount: 2100 },
    { category: 'Software', volatility: 12, drift: 8, amount: 4200 },
    { category: 'Other', volatility: 55, drift: 15, amount: 2800 },
  ];

  // Discretionary vs Non-Discretionary
  const discretionaryTotal = 14500; // Contractors + Marketing + Other
  const nonDiscretionaryTotal = 31300; // Payroll + Utilities + Software
  const discretionaryPercent = Math.round((discretionaryTotal / (discretionaryTotal + nonDiscretionaryTotal)) * 100);

  // Upcoming Commitments (mock data - would come from obligations)
  const upcomingCommitments = [
    { name: 'Payroll', due: '2024-01-15', amount: 25000, type: 'fixed' },
    { name: 'Office Rent', due: '2024-01-01', amount: 4500, type: 'fixed' },
    { name: 'AWS', due: '2024-01-05', amount: 1200, type: 'fixed' },
    { name: 'Insurance', due: '2024-01-10', amount: 800, type: 'fixed' },
    { name: 'Tax Payment', due: '2024-01-20', amount: 8500, type: 'quarterly' },
  ];

  // Cash Discipline Metrics
  const bufferIntegrity = Math.round(
    (parseFloat(insights.cash_discipline.current_buffer) /
      parseFloat(insights.cash_discipline.target_buffer)) * 100
  );
  const daysBelowTarget = insights.cash_discipline.days_below_target_last_90;

  // Buffer Trend / Burn Momentum
  const bufferTrendData = [
    { week: 'W1', buffer: 48000, target: 50000 },
    { week: 'W2', buffer: 45000, target: 50000 },
    { week: 'W3', buffer: 52000, target: 50000 },
    { week: 'W4', buffer: 49000, target: 50000 },
    { week: 'W5', buffer: 47000, target: 50000 },
    { week: 'W6', buffer: 51000, target: 50000 },
    { week: 'W7', buffer: 53000, target: 50000 },
    { week: 'W8', buffer: 50000, target: 50000 },
  ];

  // Burn momentum calculation (weekly change rate)
  const burnMomentum = ((bufferTrendData[7].buffer - bufferTrendData[0].buffer) / bufferTrendData[0].buffer) * 100;

  // Reactive vs Deliberate - decisions made under buffer stress
  const totalDecisions = 24;
  const reactiveDecisions = 7;
  const reactivePercent = Math.round((reactiveDecisions / totalDecisions) * 100);

  // ============================================================================
  // TRIGGERED SCENARIOS - Auto-generated from behavior thresholds
  // ============================================================================
  const triggeredScenarios = [];

  // Check for payment reliability triggers
  const unreliableTopClients = paymentReliabilityData.filter(
    c => c.trend === 'worsening' &&
    clientConcentrationData.find(cc => cc.name === c.client_name && cc.value > 15)
  );
  if (unreliableTopClients.length > 0) {
    triggeredScenarios.push({
      trigger: 'Payment Reliability Drop',
      scenario: `${unreliableTopClients[0].client_name} pays 21 days late for 2 cycles`,
      impact: 'high',
      actions: ['Draft chase sequence', 'Adjust forecast confidence', 'Recommend buffer hold'],
    });
  }

  // Check for expense drift triggers
  const driftingCategories = expenseVolatilityData.filter(e => e.drift > 10);
  if (driftingCategories.length > 0) {
    triggeredScenarios.push({
      trigger: 'Expense Drift',
      scenario: `${driftingCategories[0].category} spend +${driftingCategories[0].drift}% for 6 weeks`,
      impact: 'medium',
      actions: ['Flag approvals', 'Cap category', 'Suggest alternatives'],
    });
  }

  // Check for buffer integrity triggers
  if (bufferIntegrity < 100) {
    triggeredScenarios.push({
      trigger: 'Buffer Integrity Breach',
      scenario: `Buffer below target for ${daysBelowTarget} days`,
      impact: daysBelowTarget > 14 ? 'high' : 'medium',
      actions: ['AR escalation', 'AP reprioritization', 'Spending freeze review'],
    });
  }

  // Health Score trend data (would come from API in production)
  const currentScore = insights.summary.overall_health_score;
  const healthScoreTrendData = [
    { week: 'W1', score: 45, date: '6 weeks ago' },
    { week: 'W2', score: 48, date: '5 weeks ago' },
    { week: 'W3', score: 52, date: '4 weeks ago' },
    { week: 'W4', score: 49, date: '3 weeks ago' },
    { week: 'W5', score: 55, date: '2 weeks ago' },
    { week: 'W6', score: currentScore, date: 'Current' },
  ];

  // Calculate trend direction
  const scoreTrend = currentScore - healthScoreTrendData[0].score;
  const getScoreStatus = (score: number) => {
    if (score >= 81) return { label: 'Excellent', color: 'text-lime', bgColor: 'bg-lime/10', borderColor: 'border-lime/30' };
    if (score >= 61) return { label: 'Healthy', color: 'text-lime', bgColor: 'bg-lime/10', borderColor: 'border-lime/30' };
    if (score >= 41) return { label: 'At Risk', color: 'text-amber-600', bgColor: 'bg-amber-50', borderColor: 'border-amber-200' };
    return { label: 'Critical', color: 'text-tomato', bgColor: 'bg-tomato/10', borderColor: 'border-tomato/30' };
  };
  const scoreStatus = getScoreStatus(currentScore);

  return (
    <div className="min-h-screen p-6 space-y-6">
      {/* Health Score Section - Compact Layout: Chart Left, Insights Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Health Score Chart - Left Side */}
        <GlassCard variant="solid" className="lg:col-span-2">
          <GlassCardHeader className="pb-2">
            <div className="flex items-start justify-between">
              <div>
                <GlassCardTitle className="text-gunmetal">Health Score</GlassCardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">Cash flow health trend</p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-gunmetal">{currentScore}</span>
                    <span className="text-sm text-muted-foreground">/100</span>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Badge className={`${scoreStatus.bgColor} ${scoreStatus.color} ${scoreStatus.borderColor} border text-xs`}>
                    {scoreStatus.label}
                  </Badge>
                  {scoreTrend !== 0 && (
                    <div className={`flex items-center gap-1 text-xs ${scoreTrend > 0 ? 'text-lime' : 'text-tomato'}`}>
                      {scoreTrend > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                      <span className="font-medium">{scoreTrend > 0 ? '+' : ''}{scoreTrend}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </GlassCardHeader>
          <GlassCardContent className="pt-0">
            <ChartContainer
              config={{
                score: { label: 'Health Score', color: '#112331' },
              }}
              className="h-[160px] w-full"
            >
              <AreaChart data={healthScoreTrendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="healthScoreGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#112331" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#112331" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <ReferenceArea y1={0} y2={40} fill="#FF4F3F" fillOpacity={0.08} />
                <ReferenceArea y1={40} y2={60} fill="#F59E0B" fillOpacity={0.06} />
                <ReferenceArea y1={60} y2={80} fill="#C5FF35" fillOpacity={0.08} />
                <ReferenceArea y1={80} y2={100} fill="#C5FF35" fillOpacity={0.12} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                <XAxis
                  dataKey="week"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: '#9ca3af' }}
                  tickMargin={6}
                />
                <YAxis
                  domain={[0, 100]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: '#9ca3af' }}
                  ticks={[0, 40, 60, 80, 100]}
                  width={25}
                />
                <ChartTooltip
                  cursor={{ stroke: '#112331', strokeWidth: 1, strokeDasharray: '4 4' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      const status = getScoreStatus(data.score);
                      return (
                        <div className="rounded-lg border bg-background p-2 shadow-xl">
                          <p className="text-xs text-muted-foreground">{data.date}</p>
                          <div className="flex items-center gap-2">
                            <span className="text-lg font-bold text-gunmetal">{data.score}</span>
                            <Badge className={`${status.bgColor} ${status.color} text-xs`}>
                              {status.label}
                            </Badge>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#112331"
                  strokeWidth={2}
                  fill="url(#healthScoreGradient)"
                  dot={{ fill: '#112331', strokeWidth: 0, r: 3 }}
                  activeDot={{ fill: '#112331', strokeWidth: 2, stroke: '#fff', r: 5 }}
                />
              </AreaChart>
            </ChartContainer>
            {/* Compact Legend */}
            <div className="flex items-center justify-center gap-4 mt-2 pt-2 border-t border-gray-100">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm bg-tomato/20 border border-tomato/30" />
                <span className="text-[10px] text-muted-foreground">Critical</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm bg-amber-100 border border-amber-200" />
                <span className="text-[10px] text-muted-foreground">At Risk</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm bg-lime/20 border border-lime/30" />
                <span className="text-[10px] text-muted-foreground">Healthy</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-sm bg-lime/30 border border-lime/40" />
                <span className="text-[10px] text-muted-foreground">Excellent</span>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>

        {/* Right Side - Stacked Insights & Scenarios */}
        <div className="flex flex-col gap-4">
          {/* Current Situation - Compact */}
          <GlassCard variant="solid" className="flex-1">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="text-gunmetal text-sm">Current Situation</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent className="pt-0">
              <ul className="space-y-2">
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-gunmetal mt-1.5 flex-shrink-0" />
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {clientConcentrationData[0]?.value > 40
                      ? `High concentration: ${clientConcentrationData[0]?.name} is ${clientConcentrationData[0]?.value.toFixed(0)}% of revenue`
                      : 'Revenue well diversified across clients'}
                  </p>
                </li>
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-gunmetal mt-1.5 flex-shrink-0" />
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {driftingCategories.length > 0
                      ? `${driftingCategories[0].category} spending drifting +${driftingCategories[0].drift}%`
                      : 'Expense patterns stable'}
                  </p>
                </li>
                <li className="flex items-start gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-gunmetal mt-1.5 flex-shrink-0" />
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {bufferIntegrity < 100
                      ? `Buffer at ${bufferIntegrity}% of target`
                      : 'Cash buffer healthy'}
                  </p>
                </li>
              </ul>
            </GlassCardContent>
          </GlassCard>

          {/* Suggested Scenarios - Compact */}
          <GlassCard variant="solid" className="flex-1">
            <GlassCardHeader className="pb-2">
              <GlassCardTitle className="text-gunmetal text-sm">Suggested Scenarios</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent className="pt-0">
              {triggeredScenarios.length > 0 ? (
                <div className="space-y-2">
                  {triggeredScenarios.slice(0, 2).map((scenario, index) => (
                    <div
                      key={index}
                      className={`flex items-center justify-between gap-2 p-2 rounded-lg border ${
                        scenario.impact === 'high'
                          ? 'bg-tomato/5 border-tomato/20'
                          : 'bg-amber-50/50 border-amber-200/50'
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <Badge
                          variant="outline"
                          className={`${
                            scenario.impact === 'high'
                              ? 'bg-tomato/10 text-tomato border-tomato/30'
                              : 'bg-amber-100 text-amber-700 border-amber-300'
                          } text-[10px] px-1.5 py-0`}
                        >
                          {scenario.trigger}
                        </Badge>
                      </div>
                      <Link to="/scenarios" className="flex-shrink-0">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-6 px-2 text-[10px] font-medium hover:bg-gunmetal hover:text-white"
                        >
                          Run
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 p-2 rounded-lg bg-lime/10 border border-lime/20">
                  <TrendingUp className="h-4 w-4 text-lime flex-shrink-0" />
                  <p className="text-xs text-muted-foreground">All patterns healthy</p>
                </div>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>

      {/* Behaviour Tabs */}
      <Tabs defaultValue="client" className="space-y-6">
        <TabsList className="glass-strong h-14 p-1.5 rounded-2xl gap-1 w-fit shadow-lg shadow-black/5">
          <TabsTrigger
            value="client"
            className="rounded-xl px-6 py-2.5 text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80"
          >
            Client Behaviour
          </TabsTrigger>
          <TabsTrigger
            value="expense"
            className="rounded-xl px-6 py-2.5 text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80"
          >
            Expense Behaviour
          </TabsTrigger>
          <TabsTrigger
            value="cash"
            className="rounded-xl px-6 py-2.5 text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80"
          >
            Cash Discipline
          </TabsTrigger>
        </TabsList>

        {/* ================================================================== */}
        {/* CLIENT BEHAVIOR TAB - Predictability + Risk                        */}
        {/* ================================================================== */}
        <TabsContent value="client" className="space-y-6">
          <p className="text-sm text-muted-foreground">
            Measures client predictability and concentration risk to inform revenue forecasts and trigger collection actions.
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Client Concentration (Cash-Weighted) - Interactive */}
            <GlassCard variant="solid" data-chart="concentration-chart">
              <ChartStyle id="concentration-chart" config={clientChartConfig} />
              <GlassCardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <GlassCardTitle className="text-gunmetal">
                      Client Concentration
                    </GlassCardTitle>
                    <p className="text-xs text-muted-foreground">Cash-weighted revenue share</p>
                  </div>
                  <Select value={selectedMonth} onValueChange={setSelectedMonth}>
                    <SelectTrigger className="h-8 w-[140px] rounded-lg text-xs">
                      <SelectValue placeholder="Select period" />
                    </SelectTrigger>
                    <SelectContent align="end" className="rounded-xl">
                      {CONCENTRATION_MONTHS.map((month) => (
                        <SelectItem key={month.key} value={month.key} className="rounded-lg text-xs">
                          {month.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </GlassCardHeader>
              <GlassCardContent>
                <ChartContainer
                  id="concentration-chart"
                  config={clientChartConfig}
                  className="mx-auto aspect-square max-w-[220px]"
                >
                  <PieChart>
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent hideLabel />}
                    />
                    <Pie
                      data={clientConcentrationData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      strokeWidth={4}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                      activeIndex={0}
                      activeShape={(props: { outerRadius?: number }) => (
                        <g>
                          <Sector {...props} outerRadius={(props.outerRadius || 0) + 8} />
                          <Sector
                            {...props}
                            outerRadius={(props.outerRadius || 0) + 18}
                            innerRadius={(props.outerRadius || 0) + 10}
                          />
                        </g>
                      )}
                    >
                      <Label
                        content={({ viewBox }) => {
                          if (viewBox && 'cx' in viewBox && 'cy' in viewBox) {
                            const topClient = clientConcentrationData[0];
                            return (
                              <text
                                x={viewBox.cx}
                                y={viewBox.cy}
                                textAnchor="middle"
                                dominantBaseline="middle"
                              >
                                <tspan
                                  x={viewBox.cx}
                                  y={viewBox.cy}
                                  className="fill-gunmetal text-2xl font-bold"
                                >
                                  {topClient?.value.toFixed(0)}%
                                </tspan>
                                <tspan
                                  x={viewBox.cx}
                                  y={(viewBox.cy || 0) + 18}
                                  className="fill-muted-foreground text-xs"
                                >
                                  Top client
                                </tspan>
                              </text>
                            );
                          }
                        }}
                      />
                    </Pie>
                  </PieChart>
                </ChartContainer>
                {/* Professional Legend */}
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <div className="space-y-2.5">
                    {clientConcentrationData.map((client, index) => (
                      <div key={index} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-3 h-3 rounded-sm flex-shrink-0"
                            style={{ backgroundColor: client.fill }}
                          />
                          <span className="text-sm font-medium text-gunmetal">{client.name}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm tabular-nums text-gunmetal font-semibold">
                            {client.value.toFixed(1)}%
                          </span>
                          {client.value > 25 && (
                            <Badge variant="outline" className="bg-tomato/5 text-tomato border-tomato/20 text-xs font-medium">
                              High
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </GlassCardContent>
            </GlassCard>

            {/* Revenue at Risk */}
            <GlassCard variant="solid">
              <GlassCardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <GlassCardTitle className="text-gunmetal">
                      Revenue at Risk
                    </GlassCardTitle>
                    <p className="text-xs text-muted-foreground">Probability-weighted by payment behavior</p>
                  </div>
                  <HoverCard>
                    <HoverCardTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-muted-foreground hover:text-gunmetal">
                        <Info className="h-4 w-4" />
                      </Button>
                    </HoverCardTrigger>
                    <HoverCardContent className="w-72" align="end">
                      <div className="space-y-2">
                        <h4 className="text-sm font-semibold text-gunmetal">How is this calculated?</h4>
                        <p className="text-xs text-muted-foreground">
                          Revenue at risk is weighted by each client's payment reliability score. Clients with delayed payment patterns contribute more to the risk calculation.
                        </p>
                        <div className="pt-2 border-t">
                          <p className="text-xs text-muted-foreground">
                            <span className="font-medium">Threshold:</span> When risk exceeds 15% of revenue, a collection scenario is automatically generated.
                          </p>
                        </div>
                      </div>
                    </HoverCardContent>
                  </HoverCard>
                </div>
              </GlassCardHeader>
              <GlassCardContent className="space-y-5">
                {/* 30 Day Risk */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gunmetal">Next 30 Days</span>
                    <span className="text-2xl font-bold text-gunmetal">{formatCurrency(revenueAtRisk30)}</span>
                  </div>
                  <div className="space-y-1.5">
                    <Progress
                      value={Math.min((revenueAtRisk30 / parseFloat(insights.income_behaviour.total_monthly_revenue)) * 100, 100)}
                      className="h-2 bg-gray-100"
                    />
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        {Math.round((revenueAtRisk30 / parseFloat(insights.income_behaviour.total_monthly_revenue)) * 100)}% of revenue
                      </span>
                      {(revenueAtRisk30 / parseFloat(insights.income_behaviour.total_monthly_revenue)) * 100 > 15 ? (
                        <Badge variant="outline" className="bg-tomato/5 text-tomato border-tomato/20 text-xs">
                          Above threshold
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-lime/10 text-gunmetal border-lime/30 text-xs">
                          Within target
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* 60 Day Risk */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gunmetal">Next 60 Days</span>
                    <span className="text-2xl font-bold text-gunmetal">{formatCurrency(revenueAtRisk60)}</span>
                  </div>
                  <div className="space-y-1.5">
                    <Progress
                      value={Math.min((revenueAtRisk60 / parseFloat(insights.income_behaviour.total_monthly_revenue)) * 100, 100)}
                      className="h-2 bg-gray-100"
                    />
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        {Math.round((revenueAtRisk60 / parseFloat(insights.income_behaviour.total_monthly_revenue)) * 100)}% of revenue
                      </span>
                      {(revenueAtRisk60 / parseFloat(insights.income_behaviour.total_monthly_revenue)) * 100 > 15 ? (
                        <Badge variant="outline" className="bg-tomato/5 text-tomato border-tomato/20 text-xs">
                          Above threshold
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-lime/10 text-gunmetal border-lime/30 text-xs">
                          Within target
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* Trigger Info */}
                <div className="flex items-center gap-3 p-3 bg-amber-50/50 rounded-lg border border-amber-100">
                  <div className="flex-shrink-0 w-1 h-8 bg-amber-400 rounded-full" />
                  <p className="text-xs text-amber-800">
                    <span className="font-semibold">Trigger:</span> Revenue at risk &gt;15% generates a collection scenario
                  </p>
                </div>
              </GlassCardContent>
            </GlassCard>
          </div>

          {/* Payment Reliability Score Table */}
          <GlassCard variant="solid">
            <GlassCardHeader>
              <GlassCardTitle className="text-gunmetal">
                Payment Reliability Score
              </GlassCardTitle>
              <p className="text-xs text-muted-foreground">
                Mean days to payment + variance + trend direction
              </p>
            </GlassCardHeader>
            <GlassCardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-gray-200">
                    <TableHead className="text-muted-foreground font-normal">Client</TableHead>
                    <TableHead className="text-center text-muted-foreground font-normal">Mean Days</TableHead>
                    <TableHead className="text-center text-muted-foreground font-normal">Variance</TableHead>
                    <TableHead className="text-center text-muted-foreground font-normal">Trend</TableHead>
                    <TableHead className="text-right text-muted-foreground font-normal">Monthly</TableHead>
                    <TableHead className="text-center text-muted-foreground font-normal">Risk</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paymentReliabilityData.slice(0, 5).map((client) => (
                    <TableRow key={client.client_id} className="border-b border-gray-100">
                      <TableCell className="font-medium text-gunmetal">
                        {client.client_name}
                      </TableCell>
                      <TableCell className="text-center">
                        <span className={client.mean_days > 14 ? 'text-tomato font-medium' : 'text-gunmetal'}>
                          {client.mean_days}d
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        <span className={client.variance > 5 ? 'text-amber-600' : 'text-muted-foreground'}>
                          ±{client.variance}d
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        {client.trend === 'worsening' ? (
                          <div className="flex items-center justify-center gap-1 text-tomato">
                            <TrendingUp className="h-4 w-4" />
                            <span className="text-xs">Worsening</span>
                          </div>
                        ) : client.trend === 'improving' ? (
                          <div className="flex items-center justify-center gap-1 text-lime">
                            <TrendingDown className="h-4 w-4" />
                            <span className="text-xs">Improving</span>
                          </div>
                        ) : (
                          <div className="flex items-center justify-center gap-1 text-muted-foreground">
                            <Minus className="h-4 w-4" />
                            <span className="text-xs">Stable</span>
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-right text-gunmetal">
                        {formatCurrency(client.monthly_amount)}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          className={
                            client.risk_level === 'low'
                              ? 'bg-lime text-gunmetal'
                              : client.risk_level === 'medium'
                              ? 'bg-amber-500 text-white'
                              : 'bg-tomato text-white'
                          }
                        >
                          {client.risk_level}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </GlassCardContent>
          </GlassCard>
        </TabsContent>

        {/* ================================================================== */}
        {/* EXPENSE BEHAVIOR TAB - Volatility + Controllability               */}
        {/* ================================================================== */}
        <TabsContent value="expense" className="space-y-6">
          <p className="text-sm text-muted-foreground">
            Measures expense volatility and controllability to identify cost optimization opportunities and spending risks.
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Expense Volatility by Category */}
            <GlassCard variant="solid">
              <GlassCardHeader>
                <GlassCardTitle className="text-gunmetal">
                  Expense Volatility
                </GlassCardTitle>
                <p className="text-xs text-muted-foreground">Variance + drift by category</p>
              </GlassCardHeader>
              <GlassCardContent>
                <ChartContainer
                  config={{
                    volatility: { label: 'Volatility %', color: '#112331' },
                  }}
                  className="h-48 w-full"
                >
                  <BarChart data={expenseVolatilityData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#e5e7eb" />
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="category"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 12, fill: '#6b7280' }}
                      width={80}
                    />
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent />}
                    />
                    <Bar dataKey="volatility" fill="var(--color-volatility)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ChartContainer>
                <div className="mt-4 p-3 bg-amber-50 rounded-lg">
                  <p className="text-xs text-amber-800">
                    <strong>Trigger:</strong> Drift &gt;10% over 6 weeks generates a cost control scenario
                  </p>
                </div>
              </GlassCardContent>
            </GlassCard>

            {/* Discretionary vs Non-Discretionary */}
            <GlassCard variant="solid">
              <GlassCardHeader>
                <GlassCardTitle className="text-gunmetal">
                  Discretionary vs Non-Discretionary
                </GlassCardTitle>
                <p className="text-xs text-muted-foreground">Delayable spend identification</p>
              </GlassCardHeader>
              <GlassCardContent>
                <div className="flex items-center justify-center h-32">
                  <div className="relative w-full max-w-xs">
                    <div className="h-8 bg-gray-200 rounded-full overflow-hidden flex">
                      <div
                        className="h-full bg-lime"
                        style={{ width: `${100 - discretionaryPercent}%` }}
                      />
                      <div
                        className="h-full bg-amber-400"
                        style={{ width: `${discretionaryPercent}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <span className="w-3 h-3 rounded-full bg-lime" />
                      <span className="text-sm text-muted-foreground">Non-Discretionary</span>
                    </div>
                    <p className="text-xl font-bold text-gunmetal">{formatCurrency(nonDiscretionaryTotal)}</p>
                    <p className="text-xs text-muted-foreground">{100 - discretionaryPercent}% of spend</p>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <span className="w-3 h-3 rounded-full bg-amber-400" />
                      <span className="text-sm text-muted-foreground">Discretionary</span>
                    </div>
                    <p className="text-xl font-bold text-gunmetal">{formatCurrency(discretionaryTotal)}</p>
                    <p className="text-xs text-muted-foreground">{discretionaryPercent}% of spend</p>
                  </div>
                </div>
                <p className="text-xs text-center text-muted-foreground mt-4">
                  Discretionary spend can be delayed under buffer stress
                </p>
              </GlassCardContent>
            </GlassCard>
          </div>

          {/* Upcoming Commitments Calendar */}
          <GlassCard variant="solid">
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-muted-foreground" />
                <GlassCardTitle className="text-gunmetal">
                  Upcoming Commitments
                </GlassCardTitle>
              </div>
              <p className="text-xs text-muted-foreground">
                Fixed obligations for the next 30 days
              </p>
            </GlassCardHeader>
            <GlassCardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-b border-gray-200">
                    <TableHead className="text-muted-foreground font-normal">Commitment</TableHead>
                    <TableHead className="text-muted-foreground font-normal">Due Date</TableHead>
                    <TableHead className="text-right text-muted-foreground font-normal">Amount</TableHead>
                    <TableHead className="text-center text-muted-foreground font-normal">Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {upcomingCommitments.map((commitment, index) => (
                    <TableRow key={index} className="border-b border-gray-100">
                      <TableCell className="font-medium text-gunmetal">{commitment.name}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(commitment.due).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </TableCell>
                      <TableCell className="text-right text-gunmetal">
                        {formatCurrency(commitment.amount)}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="capitalize">
                          {commitment.type}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4 p-3 bg-gray-50 rounded-lg flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Total Commitments (30 days)</span>
                <span className="font-bold text-gunmetal">
                  {formatCurrency(upcomingCommitments.reduce((sum, c) => sum + c.amount, 0))}
                </span>
              </div>
            </GlassCardContent>
          </GlassCard>
        </TabsContent>

        {/* ================================================================== */}
        {/* CASH DISCIPLINE TAB - Control + Stress                            */}
        {/* ================================================================== */}
        <TabsContent value="cash" className="space-y-6">
          <p className="text-sm text-muted-foreground">
            Measures buffer health and decision quality to maintain financial resilience and avoid reactive spending.
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Buffer Integrity */}
            <GlassCard variant="solid">
              <GlassCardHeader>
                <GlassCardTitle className="text-gunmetal">Buffer Integrity</GlassCardTitle>
                <p className="text-xs text-muted-foreground">Current vs target + days below threshold</p>
              </GlassCardHeader>
              <GlassCardContent>
                <div className="space-y-4 mt-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Current Buffer</span>
                    <span className="font-bold text-gunmetal">
                      {formatCurrency(insights.cash_discipline.current_buffer)}
                    </span>
                  </div>
                  <div className="relative h-4 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`absolute left-0 top-0 h-full rounded-full ${
                        bufferIntegrity >= 100 ? 'bg-lime' : bufferIntegrity >= 80 ? 'bg-amber-400' : 'bg-tomato'
                      }`}
                      style={{ width: `${Math.min(bufferIntegrity, 100)}%` }}
                    />
                    <div
                      className="absolute top-0 h-full w-0.5 bg-gunmetal"
                      style={{ left: '100%', transform: 'translateX(-100%)' }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>0%</span>
                    <span className="font-medium">Target: {formatCurrency(insights.cash_discipline.target_buffer)}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-gunmetal">{bufferIntegrity}%</p>
                      <p className="text-xs text-muted-foreground">of target</p>
                    </div>
                    <div className="text-center">
                      <p className={`text-2xl font-bold ${daysBelowTarget > 14 ? 'text-tomato' : 'text-gunmetal'}`}>
                        {daysBelowTarget}
                      </p>
                      <p className="text-xs text-muted-foreground">days below (90d)</p>
                    </div>
                  </div>
                </div>
                {bufferIntegrity < 100 && (
                  <div className="mt-4 p-3 bg-tomato/10 rounded-lg">
                    <p className="text-xs text-tomato">
                      <strong>Trigger Active:</strong> Buffer below target generates stress scenarios
                    </p>
                  </div>
                )}
              </GlassCardContent>
            </GlassCard>

            {/* Buffer Trend / Burn Momentum */}
            <GlassCard variant="solid">
              <GlassCardHeader>
                <GlassCardTitle className="text-gunmetal">Buffer Trend</GlassCardTitle>
                <p className="text-xs text-muted-foreground">Direction + burn momentum (8 weeks)</p>
              </GlassCardHeader>
              <GlassCardContent>
                <ChartContainer
                  config={{
                    buffer: { label: 'Buffer', color: '#112331' },
                  }}
                  className="h-40 w-full"
                >
                  <LineChart data={bufferTrendData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis
                      dataKey="week"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                    />
                    <YAxis hide domain={['dataMin - 5000', 'dataMax + 5000']} />
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent />}
                    />
                    <ReferenceLine y={50000} stroke="#C5FF35" strokeDasharray="5 5" />
                    <Line
                      type="monotone"
                      dataKey="buffer"
                      stroke="var(--color-buffer)"
                      strokeWidth={2}
                      dot={{ fill: '#112331', strokeWidth: 0, r: 3 }}
                    />
                  </LineChart>
                </ChartContainer>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Trend</p>
                    <div className="flex items-center justify-center gap-1">
                      {burnMomentum > 0 ? (
                        <TrendingUp className="h-4 w-4 text-lime" />
                      ) : burnMomentum < 0 ? (
                        <TrendingDown className="h-4 w-4 text-tomato" />
                      ) : (
                        <Minus className="h-4 w-4 text-muted-foreground" />
                      )}
                      <span className={`font-bold ${burnMomentum > 0 ? 'text-lime' : burnMomentum < 0 ? 'text-tomato' : 'text-gunmetal'}`}>
                        {burnMomentum > 0 ? 'Building' : burnMomentum < 0 ? 'Burning' : 'Stable'}
                      </span>
                    </div>
                  </div>
                  <div className="text-center p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">Momentum</p>
                    <p className={`font-bold ${burnMomentum >= 0 ? 'text-lime' : 'text-tomato'}`}>
                      {burnMomentum >= 0 ? '+' : ''}{burnMomentum.toFixed(1)}%
                    </p>
                  </div>
                </div>
              </GlassCardContent>
            </GlassCard>
          </div>

          {/* Reactive vs Deliberate Decisions */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlassCard variant="solid">
              <GlassCardHeader>
                <GlassCardTitle className="text-gunmetal">
                  Reactive vs Deliberate Decisions
                </GlassCardTitle>
                <p className="text-xs text-muted-foreground">
                  Spending decisions made under buffer stress (last 30 days)
                </p>
              </GlassCardHeader>
              <GlassCardContent>
                <div className="flex items-center justify-center py-6">
                  <div className="relative">
                    <svg className="w-40 h-40 transform -rotate-90">
                      <circle
                        cx="80"
                        cy="80"
                        r="70"
                        stroke="#e5e7eb"
                        strokeWidth="12"
                        fill="none"
                      />
                      <circle
                        cx="80"
                        cy="80"
                        r="70"
                        stroke={reactivePercent > 30 ? '#f56565' : reactivePercent > 15 ? '#ecc94b' : '#c6f6d5'}
                        strokeWidth="12"
                        fill="none"
                        strokeDasharray={`${(reactivePercent / 100) * 440} 440`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className={`text-3xl font-bold ${reactivePercent > 30 ? 'text-tomato' : 'text-gunmetal'}`}>
                        {reactivePercent}%
                      </span>
                      <span className="text-xs text-muted-foreground">reactive</span>
                    </div>
                  </div>
                </div>
                <div className="text-center text-sm text-muted-foreground">
                  {reactiveDecisions} of {totalDecisions} decisions made while buffer was below target
                </div>
                {reactivePercent > 30 && (
                  <div className="mt-4 p-3 bg-tomato/10 rounded-lg">
                    <p className="text-xs text-tomato">
                      High reactive rate indicates spending under pressure. Consider pre-planning larger expenses.
                    </p>
                  </div>
                )}
              </GlassCardContent>
            </GlassCard>

            {/* Forecast Confidence */}
            <GlassCard variant="solid">
              <GlassCardHeader>
                <GlassCardTitle className="text-gunmetal">Forecast Confidence</GlassCardTitle>
                <p className="text-xs text-muted-foreground">
                  Data quality score for cash projections
                </p>
              </GlassCardHeader>
              <GlassCardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gunmetal">Overall Score</span>
                  <span className="font-bold text-gunmetal">79%</span>
                </div>
                <Progress value={79} className="h-2" />

                <div className="space-y-2 mt-4">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-lime" />
                      <span className="text-muted-foreground">High confidence</span>
                    </div>
                    <span className="text-gunmetal">1 items</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-amber-500" />
                      <span className="text-muted-foreground">Medium confidence</span>
                    </div>
                    <span className="text-gunmetal">32 items</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-tomato" />
                      <span className="text-muted-foreground">Low confidence</span>
                    </div>
                    <span className="text-gunmetal">2 items</span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs text-muted-foreground mb-2">
                    <strong>To improve confidence:</strong>
                  </p>
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    <li>• Link repeating invoices in Xero</li>
                    <li>• Add expected payment dates to clients</li>
                    <li>• Set up recurring expense templates</li>
                  </ul>
                </div>
              </GlassCardContent>
            </GlassCard>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
