import { useMemo } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
} from 'recharts';
import {
  ChartContainer,
  ChartTooltip,
  type ChartConfig,
} from '@/components/ui/chart';
import type { ForecastResponse } from '@/lib/api/types';
import type { DangerZone, ImpactChartData } from './types';

interface ImpactVisualizationProps {
  forecast: ForecastResponse;
  dangerZone: DangerZone | null;
  alertWeek: number;
  bufferAmount: number;
  alertImpact?: number | null; // Cash amount the alert impacts (negative = reduces cash)
  impactWeek?: number; // Week when impact starts (defaults to alertWeek)
}

const chartConfig = {
  position: { label: 'Current Forecast', color: 'var(--chart-1)' },
  impactedPosition: { label: 'If Alert Hits', color: 'var(--tomato)' },
  buffer: { label: 'Cash Buffer', color: 'var(--tomato)' },
} satisfies ChartConfig;

// Format Y-axis values
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

// Format currency for tooltip
const formatCurrency = (value: number | string) => {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
};

export function ImpactVisualization({
  forecast,
  dangerZone,
  alertWeek,
  bufferAmount,
  alertImpact,
  impactWeek,
}: ImpactVisualizationProps) {
  // The week when impact starts (defaults to alertWeek)
  const effectiveImpactWeek = impactWeek ?? alertWeek;

  // Transform forecast data for chart, including impacted scenario
  const chartData: ImpactChartData[] = useMemo(() => {
    // Compute the cumulative impact - once the impact hits, it persists
    return forecast.weeks.map((week) => {
      const position = parseFloat(week.ending_balance);
      // Apply impact from the impact week onwards
      const shouldApplyImpact = alertImpact && week.week_number >= effectiveImpactWeek;
      const impactedPosition = shouldApplyImpact ? position - Math.abs(alertImpact) : position;

      return {
        week: `Week ${week.week_number}`,
        weekNumber: week.week_number,
        position,
        impactedPosition: alertImpact ? impactedPosition : undefined,
        buffer: bufferAmount,
        isBelowBuffer: position < bufferAmount,
        isImpactedBelowBuffer: impactedPosition < bufferAmount,
        cashIn: parseFloat(week.cash_in),
        cashOut: parseFloat(week.cash_out),
      };
    });
  }, [forecast, bufferAmount, alertImpact, effectiveImpactWeek]);

  // Check if showing impact scenario
  const showImpactScenario = alertImpact && alertImpact !== 0;

  // Determine zoom window - center on the danger zone or alert week
  const zoomWindow = useMemo(() => {
    const focusWeek = dangerZone?.lowestPoint.week || alertWeek || 1;
    const windowSize = 6; // Show 6 weeks around the focus
    const start = Math.max(0, focusWeek - Math.floor(windowSize / 2) - 1);
    const end = Math.min(chartData.length, start + windowSize);
    return { start, end };
  }, [dangerZone, alertWeek, chartData.length]);

  // Get the zoomed data
  const zoomedData = chartData.slice(zoomWindow.start, zoomWindow.end);

  // Find danger zone segments for ReferenceArea
  const dangerSegments = useMemo(() => {
    if (!dangerZone || dangerZone.belowBufferWeeks.length === 0) return [];

    const segments: { x1: string; x2: string }[] = [];
    const sortedWeeks = [...dangerZone.belowBufferWeeks].sort((a, b) => a - b);

    let segmentStart = sortedWeeks[0];
    let segmentEnd = sortedWeeks[0];

    for (let i = 1; i < sortedWeeks.length; i++) {
      if (sortedWeeks[i] === segmentEnd + 1) {
        segmentEnd = sortedWeeks[i];
      } else {
        segments.push({
          x1: `Week ${segmentStart}`,
          x2: `Week ${segmentEnd + 1}`,
        });
        segmentStart = sortedWeeks[i];
        segmentEnd = sortedWeeks[i];
      }
    }
    // Add the last segment
    segments.push({
      x1: `Week ${segmentStart}`,
      x2: `Week ${segmentEnd + 1}`,
    });

    return segments;
  }, [dangerZone]);

  return (
    <div
      className="
        relative
        alert-hero-glass
        rounded-3xl
        p-8
        shadow-[0_8px_32px_rgba(255,79,63,0.12),0_4px_16px_rgba(0,0,0,0.06)]
      "
    >
      {/* Week label pill - shows the focus week */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-white/60 backdrop-blur-sm rounded-full border border-white/40">
        <span className="text-sm font-semibold text-gunmetal">
          Week {alertWeek}
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-end gap-6 text-xs text-gunmetal mb-4 mt-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-2 bg-gunmetal rounded" />
          <span>Current Forecast</span>
        </div>
        {showImpactScenario && (
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 border-b-2 border-dashed border-tomato" />
            <span>If Alert Hits</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <div className="w-6 h-0.5 border-b-2 border-dotted border-gunmetal/50" />
          <span>Cash Buffer</span>
        </div>
      </div>

      {/* Chart */}
      <ChartContainer config={chartConfig} className="h-[350px] w-full">
        <ComposedChart
          data={zoomedData}
          margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
        >
          {/* Gradient definitions */}
          <defs>
            <linearGradient id="fillPosition" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.6} />
              <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="fillImpacted" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--tomato)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--tomato)" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="dangerGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(255, 79, 63, 0.4)" />
              <stop offset="100%" stopColor="rgba(255, 79, 63, 0.1)" />
            </linearGradient>
          </defs>

          <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="rgba(0,0,0,0.1)" />

          <XAxis
            dataKey="week"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 12, fill: '#112331' }}
          />

          <YAxis
            tickFormatter={formatYAxisValue}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 12, fill: '#112331' }}
          />

          <ChartTooltip
            cursor={{ fill: 'rgba(0,0,0,0.05)' }}
            content={({ active, payload, label }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload as ImpactChartData & { cashIn: number; cashOut: number };
                return (
                  <div className="rounded-xl border bg-white/95 backdrop-blur-sm p-4 shadow-xl">
                    <p className="font-semibold mb-2">{label}</p>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between gap-4">
                        <span className="text-muted-foreground">Current Forecast:</span>
                        <span className="font-medium">{formatCurrency(data.position)}</span>
                      </div>
                      {data.impactedPosition !== undefined && (
                        <div className="flex justify-between gap-4">
                          <span className="text-tomato">If Alert Hits:</span>
                          <span className="font-medium text-tomato">{formatCurrency(data.impactedPosition)}</span>
                        </div>
                      )}
                      <div className="flex justify-between gap-4 pt-1 border-t mt-1">
                        <span className="text-muted-foreground">Buffer:</span>
                        <span className="font-medium">{formatCurrency(data.buffer)}</span>
                      </div>
                      {data.isImpactedBelowBuffer && data.impactedPosition !== undefined && (
                        <div className="flex justify-between gap-4 text-tomato font-medium">
                          <span>Impact Shortfall:</span>
                          <span>{formatCurrency(data.buffer - data.impactedPosition)}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />

          {/* Danger zone areas - render before the main area so they appear behind */}
          {dangerSegments.map((segment, index) => (
            <ReferenceArea
              key={`danger-${index}`}
              x1={segment.x1}
              x2={segment.x2}
              fill="url(#dangerGradient)"
              fillOpacity={0.5}
              strokeOpacity={0}
            />
          ))}

          {/* Cash position area - current forecast */}
          <Area
            type="monotone"
            dataKey="position"
            stroke="var(--chart-1)"
            strokeWidth={3}
            fill="url(#fillPosition)"
            fillOpacity={0.4}
            name="Current Forecast"
          />

          {/* Impacted scenario line - shows what happens if alert hits */}
          {showImpactScenario && (
            <Line
              type="monotone"
              dataKey="impactedPosition"
              stroke="var(--tomato)"
              strokeWidth={2}
              strokeDasharray="8 4"
              dot={false}
              name="If Alert Hits"
            />
          )}

          {/* Cash buffer reference line */}
          {bufferAmount > 0 && (
            <ReferenceLine
              y={bufferAmount}
              stroke="var(--gunmetal)"
              strokeDasharray="4 4"
              strokeWidth={1}
              strokeOpacity={0.5}
              label={{
                value: 'Buffer',
                position: 'right',
                fill: 'var(--gunmetal)',
                fontSize: 11,
                opacity: 0.7,
              }}
            />
          )}
        </ComposedChart>
      </ChartContainer>

      {/* Impact summary text */}
      {dangerZone && dangerZone.lowestPoint && (
        <div className="mt-4 text-center">
          <p className="text-sm text-gunmetal">
            Cash position drops to{' '}
            <span className="font-bold text-tomato">
              {formatCurrency(dangerZone.lowestPoint.amount)}
            </span>
            {' '}in Week {dangerZone.lowestPoint.week}
            {dangerZone.lowestPoint.amount < bufferAmount && (
              <>
                {' '}&mdash;{' '}
                <span className="font-bold text-tomato">
                  {formatCurrency(bufferAmount - dangerZone.lowestPoint.amount)}
                </span>
                {' '}below buffer
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
