import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { CanvasMetrics } from '@/pages/ForecastCanvas';

interface MetricsBarProps {
  metrics: CanvasMetrics;
  isLoading: boolean;
  onMetricClick: (metric: string) => void;
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatTrendPercent = (value: number) => {
  const absValue = Math.abs(value);
  if (absValue < 0.1) return '0%';
  return `${absValue >= 10 ? Math.round(absValue) : absValue.toFixed(1)}%`;
};

interface TrendData {
  direction: 'up' | 'down' | 'flat';
  percent: number;
}

interface MetricCardProps {
  label: string;
  value: string;
  status: 'good' | 'warning' | 'critical';
  subtext?: string;
  source?: string;
  trend?: TrendData;
  isHighlighted?: boolean;
  onClick?: () => void;
  isLoading?: boolean;
}

function TrendIndicator({ trend }: { trend: TrendData }) {
  const Icon = trend.direction === 'up' ? TrendingUp : trend.direction === 'down' ? TrendingDown : Minus;
  const colorClass = trend.direction === 'up'
    ? 'text-lime-dark'
    : trend.direction === 'down'
    ? 'text-tomato'
    : 'text-muted-foreground';

  return (
    <div className={cn('flex items-center gap-1 text-xs font-medium', colorClass)}>
      <Icon className="w-3.5 h-3.5" />
      <span>{formatTrendPercent(trend.percent)}</span>
    </div>
  );
}

function MetricCard({
  label,
  value,
  status,
  subtext,
  source,
  trend,
  isHighlighted,
  onClick,
  isLoading,
}: MetricCardProps) {
  const statusColor = {
    good: 'bg-lime-dark',
    warning: 'bg-amber-500',
    critical: 'bg-tomato',
  }[status];

  const valueColor = {
    good: 'text-lime-dark',
    warning: 'text-amber-500',
    critical: 'text-tomato',
  }[status];

  if (isLoading) {
    return (
      <NeuroCard className="flex-1 p-4 cursor-pointer">
        <Skeleton className="h-3 w-20 mb-2" />
        <Skeleton className="h-8 w-24 mb-1" />
        <Skeleton className="h-3 w-32" />
      </NeuroCard>
    );
  }

  return (
    <NeuroCard
      className={cn(
        'flex-1 p-4 cursor-pointer transition-all relative group hover:shadow-lg',
        isHighlighted && 'ring-2 ring-lime/30 bg-lime/5'
      )}
      onClick={onClick}
    >
      <div className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1.5">
        {label}
      </div>
      <div className="flex items-baseline gap-2">
        <span className={cn('w-2 h-2 rounded-full', statusColor)} />
        <span
          className={cn(
            'text-2xl font-bold tracking-tight text-gunmetal',
            isHighlighted && valueColor
          )}
        >
          {value}
        </span>
      </div>
      {trend && (
        <div className="flex items-center gap-1.5 mt-1.5">
          <TrendIndicator trend={trend} />
          <span className="text-[10px] text-muted-foreground">vs last week</span>
        </div>
      )}
      {subtext && !trend && (
        <div className="text-[11px] text-muted-foreground mt-1">
          {subtext}
        </div>
      )}
      {source && (
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground mt-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-lime-dark" />
          Source: {source}
        </div>
      )}
    </NeuroCard>
  );
}

export function MetricsBar({ metrics, isLoading, onMetricClick }: MetricsBarProps) {
  const getRunwayStatus = (weeks: number): 'good' | 'warning' | 'critical' => {
    if (weeks >= 12) return 'good';
    if (weeks >= 6) return 'warning';
    return 'critical';
  };

  const getCashStatus = (value: number): 'good' | 'warning' | 'critical' => {
    if (value >= 100000) return 'good';
    if (value >= 50000) return 'warning';
    return 'critical';
  };

  const getIncomeStatus = (trend?: TrendData): 'good' | 'warning' | 'critical' => {
    if (!trend) return 'good';
    if (trend.direction === 'up') return 'good';
    if (trend.direction === 'flat') return 'warning';
    return 'critical';
  };

  const getExpensesStatus = (trend?: TrendData): 'good' | 'warning' | 'critical' => {
    if (!trend) return 'warning';
    if (trend.direction === 'down') return 'good';
    if (trend.direction === 'flat') return 'warning';
    return 'critical';
  };

  return (
    <div className="flex items-stretch gap-3">
      <MetricCard
        label="Cash Position"
        value={formatCurrency(metrics.cashPosition)}
        status={getCashStatus(metrics.cashPosition)}
        trend={metrics.trends?.cashPosition}
        onClick={() => onMetricClick('cashPosition')}
        isLoading={isLoading}
      />

      <MetricCard
        label="Income (30d)"
        value={formatCurrency(metrics.income30d)}
        status={getIncomeStatus(metrics.trends?.income)}
        trend={metrics.trends?.income}
        onClick={() => onMetricClick('income')}
        isLoading={isLoading}
      />

      <MetricCard
        label="Expenses (30d)"
        value={formatCurrency(metrics.expenses30d)}
        status={getExpensesStatus(metrics.trends?.expenses)}
        trend={metrics.trends?.expenses}
        onClick={() => onMetricClick('expenses')}
        isLoading={isLoading}
      />

      <MetricCard
        label="Runway"
        value={`${metrics.runwayWeeks} weeks`}
        status={getRunwayStatus(metrics.runwayWeeks)}
        trend={metrics.trends?.runway}
        onClick={() => onMetricClick('runway')}
        isLoading={isLoading}
      />
    </div>
  );
}
