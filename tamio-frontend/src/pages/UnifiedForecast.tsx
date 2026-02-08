import { useState, useMemo, useCallback, useEffect } from 'react';
import { AlertTriangle, RefreshCw, Activity } from 'lucide-react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { useAuth } from '@/contexts/AuthContext';
import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ProjectionsTable } from '@/components/projections/ProjectionsTable';
import { transformForecastToProjections } from '@/components/projections/types';
import type { ProjectionsTableData } from '@/components/projections/types';
import type { Scenario, ScenarioSuggestion } from '@/lib/api/types';
import { deleteScenario } from '@/lib/api/scenarios';

// Import unified forecast components
import {
  UnifiedForecastProvider,
  useUnifiedForecastContext,
  useUnifiedForecast,
  ExtendedScenarioToggle,
  ScenarioPanel,
  MobileScenarioDrawer,
  type TimeRange,
  type Granularity,
} from '@/components/unified-forecast';

// Import ManualScenarioModal
import { ManualScenarioModal, type ManualScenarioParams } from '@/components/forecast/ManualScenarioModal';
import { createScenario, buildScenario } from '@/lib/api/scenarios';

// ============================================================================
// Hook: useMediaQuery
// ============================================================================

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    if (media.matches !== matches) {
      setMatches(media.matches);
    }
    const listener = () => setMatches(media.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [matches, query]);

  return matches;
}

// ============================================================================
// Formatting Helpers
// ============================================================================

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatYAxis = (value: number): string => {
  if (Math.abs(value) >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1000) {
    return `$${Math.round(value / 1000)}K`;
  }
  return `$${value}`;
};

// ============================================================================
// Time Range Toggle
// ============================================================================

interface TimeRangeToggleProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

function TimeRangeToggle({ value, onChange }: TimeRangeToggleProps) {
  return (
    <Tabs value={value} onValueChange={v => onChange(v as TimeRange)}>
      <TabsList className="bg-muted/50 h-8">
        <TabsTrigger value="13" className="text-xs px-3 h-6">
          13w
        </TabsTrigger>
        <TabsTrigger value="26" className="text-xs px-3 h-6">
          26w
        </TabsTrigger>
        <TabsTrigger value="52" className="text-xs px-3 h-6">
          52w
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}

// ============================================================================
// Granularity Toggle
// ============================================================================

interface GranularityToggleProps {
  value: Granularity;
  onChange: (granularity: Granularity) => void;
}

function GranularityToggle({ value, onChange }: GranularityToggleProps) {
  return (
    <Tabs value={value} onValueChange={v => onChange(v as Granularity)}>
      <TabsList className="bg-muted/50 h-8">
        <TabsTrigger value="weekly" className="text-xs px-3 h-6">
          Weekly
        </TabsTrigger>
        <TabsTrigger value="monthly" className="text-xs px-3 h-6">
          Monthly
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}

// ============================================================================
// Chart Tooltip
// ============================================================================

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;

  return (
    <div className="bg-white/95 backdrop-blur-sm rounded-lg p-3 shadow-lg border border-gray-200 min-w-[180px]">
      <div className="text-sm font-medium text-gunmetal mb-2">
        Week {data.weekNumber} · {data.date}
      </div>
      <div className="space-y-1.5 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Position</span>
          <span className="font-semibold">{formatCurrency(data.position)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Cash In</span>
          <span className="text-lime-dark font-medium">+{formatCurrency(data.cashIn)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Cash Out</span>
          <span className="text-tomato font-medium">-{formatCurrency(data.cashOut)}</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Forecast Chart Section
// ============================================================================

interface ForecastChartSectionProps {
  isLoading: boolean;
  disabledItems: Set<string>;
  showConfidence: boolean;
  onToggleConfidence: () => void;
}

function ForecastChartSection({ isLoading, disabledItems, showConfidence, onToggleConfidence }: ForecastChartSectionProps) {
  const { forecast, appliedScenarios, timeRange, setTimeRange } = useUnifiedForecastContext();

  // Transform forecast to chart data - base forecast (all items enabled)
  const chartData = useMemo(() => {
    if (!forecast) return [];

    let runningBalance = parseFloat(forecast.weeks[0]?.starting_balance || '0');

    return forecast.weeks.map((week, index) => {
      let cashIn = 0;
      let cashOut = 0;

      week.events.forEach(event => {
        const amount = parseFloat(event.amount);
        if (event.direction === 'in') {
          cashIn += amount;
        } else {
          cashOut += amount;
        }
      });

      const netChange = cashIn - cashOut;
      const position = runningBalance + netChange;
      runningBalance = position;

      // Calculate confidence intervals (uncertainty grows over time)
      const uncertaintyFactor = 1 + (index * 0.02); // 2% increase per week
      const variance = position * 0.12 * uncertaintyFactor; // Base 12% variance

      return {
        weekNumber: index,
        date: week.week_start,
        position,
        cashIn,
        cashOut,
        netChange,
        bestCase: position + variance,
        worstCase: Math.max(0, position - variance),
        confidence: index < 4 ? 'high' : index < 8 ? 'medium' : 'low',
      };
    });
  }, [forecast]);

  // Calculate scenario data - forecast with disabled items removed
  const scenarioData = useMemo(() => {
    if (!forecast || disabledItems.size === 0) return null;

    let runningBalance = parseFloat(forecast.weeks[0]?.starting_balance || '0');

    return forecast.weeks.map((week, index) => {
      let cashIn = 0;
      let cashOut = 0;

      week.events.forEach(event => {
        const eventName = event.source_name || event.category || 'Other';
        // Skip disabled items
        if (disabledItems.has(eventName)) return;

        const amount = parseFloat(event.amount);
        if (event.direction === 'in') {
          cashIn += amount;
        } else {
          cashOut += amount;
        }
      });

      const netChange = cashIn - cashOut;
      const position = runningBalance + netChange;
      runningBalance = position;

      return {
        weekNumber: index,
        date: week.week_start,
        scenarioPosition: position,
      };
    });
  }, [forecast, disabledItems]);

  // Merge base and scenario data
  const mergedChartData = useMemo(() => {
    if (!scenarioData) return chartData.map(d => ({ ...d, scenarioPosition: undefined as number | undefined }));
    return chartData.map((base, index) => ({
      ...base,
      scenarioPosition: scenarioData[index]?.scenarioPosition,
    }));
  }, [chartData, scenarioData]);

  // Calculate Y axis domain (include confidence bands when enabled)
  const yDomain = useMemo(() => {
    if (!mergedChartData.length) return [0, 500000];
    const allValues = mergedChartData.flatMap(d => {
      const values = [d.position, d.scenarioPosition].filter((v): v is number => v !== undefined);
      if (showConfidence) {
        values.push(d.bestCase, d.worstCase);
      }
      return values;
    });
    const max = Math.max(...allValues) * 1.1;
    const min = Math.min(...allValues, 0) * 0.9;
    return [Math.floor(min / 50000) * 50000, Math.ceil(max / 50000) * 50000];
  }, [mergedChartData, showConfidence]);

  // Buffer threshold (example: 20% of starting balance)
  const bufferThreshold = useMemo(() => {
    if (!chartData.length) return 100000;
    return chartData[0].position * 0.2;
  }, [chartData]);

  // Check if scenario shows impact
  const hasScenarioImpact = disabledItems.size > 0;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Loading chart...</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Chart Header - Legend + Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-gunmetal rounded" />
            <span className="text-muted-foreground">Base Forecast</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 border-t-2 border-dashed border-amber-500" />
            <span className="text-muted-foreground">Cash Buffer</span>
          </div>
          {showConfidence && (
            <>
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 border-t-2 border-dashed border-green-500" />
                <span className="text-muted-foreground">Best Case</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-4 h-0.5 border-t-2 border-dashed border-red-500" />
                <span className="text-muted-foreground">Worst Case</span>
              </div>
            </>
          )}
          {hasScenarioImpact && (
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 bg-purple-500 rounded" />
              <span className="text-muted-foreground">Without Disabled Items</span>
            </div>
          )}
          {appliedScenarios.map(scenario => (
            <div key={scenario.id} className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 rounded" style={{ backgroundColor: scenario.color }} />
              <span className="text-muted-foreground">{scenario.name}</span>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          <Button
            variant={showConfidence ? 'default' : 'outline'}
            size="sm"
            onClick={onToggleConfidence}
            className={`flex items-center gap-1.5 h-7 text-xs ${
              showConfidence
                ? 'bg-gunmetal hover:bg-gunmetal/90 text-white'
                : 'bg-white/50 hover:bg-white border-white/30'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Confidence
          </Button>
          <TimeRangeToggle value={timeRange} onChange={setTimeRange} />
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 px-4 pb-4">
        {mergedChartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={mergedChartData} margin={{ top: 10, right: 30, bottom: 10, left: 10 }}>
              <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#112331" stopOpacity={0.1} />
                  <stop offset="100%" stopColor="#112331" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="scenarioGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.1} />
                  <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="confidenceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22C55E" stopOpacity={0.15} />
                  <stop offset="50%" stopColor="#F59E0B" stopOpacity={0.08} />
                  <stop offset="100%" stopColor="#EF4444" stopOpacity={0.15} />
                </linearGradient>
              </defs>

              <CartesianGrid stroke="rgba(17, 35, 49, 0.08)" strokeDasharray="0" vertical={false} />

              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#6B7280', fontSize: 10 }}
                dy={10}
              />

              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#6B7280', fontSize: 10 }}
                tickFormatter={formatYAxis}
                domain={yDomain}
                dx={-10}
              />

              {/* Buffer Reference Line */}
              <ReferenceLine
                y={bufferThreshold}
                stroke="#F59E0B"
                strokeWidth={2}
                strokeDasharray="8 4"
                label={{
                  value: `Buffer ${formatYAxis(bufferThreshold)}`,
                  position: 'right',
                  fill: '#6B7280',
                  fontSize: 10,
                  fontWeight: 500,
                }}
              />

              {/* Area fill for base */}
              <Area
                type="monotone"
                dataKey="position"
                fill="url(#areaGradient)"
                stroke="none"
              />

              {/* Scenario line - when items are disabled */}
              {hasScenarioImpact && (
                <>
                  <Area
                    type="monotone"
                    dataKey="scenarioPosition"
                    fill="url(#scenarioGradient)"
                    stroke="none"
                  />
                  <Line
                    type="monotone"
                    dataKey="scenarioPosition"
                    stroke="#8B5CF6"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    dot={{ r: 3, fill: '#8B5CF6', stroke: 'white', strokeWidth: 1 }}
                    activeDot={{ r: 5, stroke: '#8B5CF6', strokeWidth: 2, fill: 'white' }}
                  />
                </>
              )}

              {/* Main forecast line */}
              <Line
                type="monotone"
                dataKey="position"
                stroke="#112331"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#112331', stroke: 'white', strokeWidth: 2 }}
                activeDot={{ r: 6, stroke: '#112331', strokeWidth: 2, fill: 'white' }}
              />

              {/* Confidence bands - shown when confidence layer is active (rendered last to be on top) */}
              {showConfidence && (
                <>
                  <Line
                    type="monotone"
                    dataKey="bestCase"
                    stroke="#22C55E"
                    strokeWidth={1.5}
                    strokeDasharray="4 2"
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="worstCase"
                    stroke="#EF4444"
                    strokeWidth={1.5}
                    strokeDasharray="4 2"
                    dot={false}
                  />
                </>
              )}

              <Tooltip content={<ChartTooltip />} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-muted-foreground">
            No forecast data available
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Content Component
// ============================================================================

function UnifiedForecastContent() {
  const { user } = useAuth();
  const isMobile = useMediaQuery('(max-width: 1024px)');

  // Context state
  const {
    forecast,
    scenarios,
    suggestions,
    appliedScenarios,
    scenarioView,
    granularity,
    setGranularity,
    isLoading,
    isScenarioLoading,
    error,
    setError,
  } = useUnifiedForecastContext();

  // Data fetching hook
  const {
    fetchForecast,
    fetchScenarios,
    runScenario,
    runSuggestedScenario,
    removeScenario,
  } = useUnifiedForecast();

  // Local state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loadingScenarioId, setLoadingScenarioId] = useState<string | null>(null);
  const [disabledItems, setDisabledItems] = useState<Set<string>>(new Set());
  const [showConfidence, setShowConfidence] = useState(false);

  // Register TAMI page context
  useTAMIPageContext({
    page: 'unified-forecast',
    pageData: {
      scenarioView,
      appliedScenarios: appliedScenarios.map(s => s.id),
    },
  });

  // Transform forecast to table data
  const tableData: ProjectionsTableData | null = useMemo(() => {
    if (!forecast) return null;
    const weeksToShow = granularity === 'weekly' ? 13 : 6;
    return transformForecastToProjections(forecast, weeksToShow);
  }, [forecast, granularity]);

  // Toggle item filter
  const handleToggleItem = useCallback((itemId: string) => {
    setDisabledItems(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }, []);

  // Handle running suggested scenario
  const handleRunSuggested = useCallback(
    async (suggestion: ScenarioSuggestion) => {
      setLoadingScenarioId(`suggestion-${suggestion.scenario_type}`);
      try {
        await runSuggestedScenario(suggestion);
      } finally {
        setLoadingScenarioId(null);
      }
    },
    [runSuggestedScenario]
  );

  // Handle applying saved scenario
  const handleApplySaved = useCallback(
    async (scenario: Scenario) => {
      if (appliedScenarios.some(s => s.id === scenario.id)) {
        removeScenario(scenario.id);
        return;
      }

      setLoadingScenarioId(scenario.id);
      try {
        await runScenario(scenario);
      } finally {
        setLoadingScenarioId(null);
      }
    },
    [appliedScenarios, runScenario, removeScenario]
  );

  // Handle delete scenario
  const handleDeleteScenario = useCallback(
    async (scenarioId: string) => {
      try {
        await deleteScenario(scenarioId);
        await fetchScenarios();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete scenario');
      }
    },
    [fetchScenarios, setError]
  );

  // Handle building new scenario from modal
  const handleBuildScenario = useCallback(
    async (params: ManualScenarioParams) => {
      if (!user?.id) return;

      try {
        const newScenario = await createScenario({
          user_id: user.id,
          name: params.name,
          scenario_type: params.type,
          entry_path: 'user_defined',
          scope_config: { effective_date: params.effectiveDate },
          parameters: params.params,
        });

        await buildScenario(newScenario.id);
        await fetchScenarios();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create scenario');
        throw err;
      }
    },
    [user?.id, fetchScenarios, setError]
  );

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gunmetal">Forecast & Scenarios</h1>
        </div>
        <NeuroCard className="p-8 text-center">
          <AlertTriangle className="w-12 h-12 mx-auto text-amber-500 mb-4" />
          <h3 className="text-lg font-semibold mb-2">Failed to load forecast</h3>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Button onClick={fetchForecast}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </NeuroCard>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gunmetal">Forecast & Scenarios</h1>
        </div>

        {/* Mobile scenario trigger */}
        {isMobile && (
          <MobileScenarioDrawer
            suggestions={suggestions}
            savedScenarios={scenarios}
            isLoading={isScenarioLoading}
            loadingScenarioId={loadingScenarioId}
            onRunSuggested={handleRunSuggested}
            onApplySaved={handleApplySaved}
            onDeleteScenario={handleDeleteScenario}
            onCreateNew={() => setShowCreateModal(true)}
          />
        )}
      </div>

      {/* Forecast Chart - Full Width */}
      <NeuroCard className="h-[640px] overflow-hidden">
        <ForecastChartSection
          isLoading={isLoading}
          disabledItems={disabledItems}
          showConfidence={showConfidence}
          onToggleConfidence={() => setShowConfidence(!showConfidence)}
        />
      </NeuroCard>

      {/* Scenario Panel (desktop only) - Below chart */}
      {!isMobile && (
        <NeuroCard className="overflow-hidden">
          <ScenarioPanel
            suggestions={suggestions}
            savedScenarios={scenarios}
            isLoading={isScenarioLoading}
            loadingScenarioId={loadingScenarioId}
            onRunSuggested={handleRunSuggested}
            onApplySaved={handleApplySaved}
            onDeleteScenario={handleDeleteScenario}
            onCreateNew={() => setShowCreateModal(true)}
          />
        </NeuroCard>
      )}

      {/* Projections Table - Full Width */}
      <NeuroCard className="p-6">
        {/* Table Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
          <ExtendedScenarioToggle />
          <GranularityToggle value={granularity} onChange={setGranularity} />
        </div>

        {/* Table */}
        <ProjectionsTable
          data={tableData}
          scenarioView={scenarioView}
          isLoading={isLoading}
          disabledItems={disabledItems}
          onToggleItem={handleToggleItem}
        />
      </NeuroCard>

      {/* Legend */}
      {!isLoading && tableData && (
        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-lime" />
            <span>Income</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tomato" />
            <span>Costs</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-lime-dark" />
            <span>High confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Medium confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tomato" />
            <span>Low confidence</span>
          </div>
        </div>
      )}

      {/* Create Scenario Modal */}
      <ManualScenarioModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onBuild={handleBuildScenario}
      />
    </div>
  );
}

// ============================================================================
// Main Page Component (with Provider)
// ============================================================================

export default function UnifiedForecast() {
  return (
    <UnifiedForecastProvider>
      <UnifiedForecastContent />
    </UnifiedForecastProvider>
  );
}
