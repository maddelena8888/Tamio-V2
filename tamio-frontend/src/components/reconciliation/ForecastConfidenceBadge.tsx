import { cn } from '@/lib/utils';
import { Activity, Info, AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { ForecastImpactSeverity } from '@/lib/api/types';

interface ForecastConfidenceBadgeProps {
  score: number; // 0-100
  unreconciledCount?: number;
  linkToLedger?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

function getSeverity(score: number): ForecastImpactSeverity {
  if (score >= 85) return 'healthy';
  if (score >= 70) return 'warning';
  return 'critical';
}

const severityConfig: Record<ForecastImpactSeverity, {
  bg: string;
  text: string;
  icon: typeof Activity;
}> = {
  healthy: {
    bg: 'bg-lime/20',
    text: 'text-lime-dark',
    icon: Activity,
  },
  warning: {
    bg: 'bg-amber-100',
    text: 'text-amber-700',
    icon: Info,
  },
  critical: {
    bg: 'bg-tomato/20',
    text: 'text-tomato',
    icon: AlertTriangle,
  },
};

export function ForecastConfidenceBadge({
  score,
  unreconciledCount = 0,
  linkToLedger = false,
  className,
  size = 'md',
}: ForecastConfidenceBadgeProps) {
  const severity = getSeverity(score);
  const config = severityConfig[severity];
  const Icon = config.icon;

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1.5 text-sm',
    lg: 'px-4 py-2 text-base',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const content = (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full',
        config.bg,
        config.text,
        sizeClasses[size],
        className
      )}
    >
      <Icon className={iconSizes[size]} />
      <span className="font-medium">
        Forecast Accuracy: {Math.round(score)}%
      </span>
      {severity !== 'healthy' && unreconciledCount > 0 && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className={cn(iconSizes[size], 'opacity-70 cursor-help')} />
          </TooltipTrigger>
          <TooltipContent>
            {unreconciledCount} unreconciled transaction{unreconciledCount !== 1 ? 's' : ''} affecting accuracy
          </TooltipContent>
        </Tooltip>
      )}
    </div>
  );

  if (linkToLedger && severity !== 'healthy') {
    return (
      <Link
        to="/ledger?tab=reconciliation"
        className="hover:opacity-80 transition-opacity"
      >
        {content}
      </Link>
    );
  }

  return content;
}

export default ForecastConfidenceBadge;
