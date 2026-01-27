import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import type { HealthRingData, HealthStatus } from '@/lib/api/health';

// ============================================================================
// Types
// ============================================================================

export type RingSize = 'sm' | 'md' | 'lg' | 'xl';
export type RingMetric = 'runway' | 'liquidity' | 'cash_velocity';

export interface HealthRingProps {
  /** The metric type (determines color) */
  metric: RingMetric;
  /** Ring data from API */
  data: HealthRingData;
  /** Ring size variant */
  size?: RingSize;
  /** Whether to animate the ring fill on mount */
  animate?: boolean;
  /** Click handler for navigation/details */
  onClick?: () => void;
  /** Additional class names */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

const RING_SIZES: Record<RingSize, { container: number; strokeWidth: number; fontSize: number; labelSize: number }> = {
  sm: { container: 140, strokeWidth: 10, fontSize: 28, labelSize: 11 },
  md: { container: 180, strokeWidth: 12, fontSize: 36, labelSize: 12 },
  lg: { container: 220, strokeWidth: 14, fontSize: 48, labelSize: 14 },
  xl: { container: 260, strokeWidth: 16, fontSize: 56, labelSize: 15 },
};

// Status-based colors: green (good), pink (warning), red (critical)
const STATUS_COLORS: Record<HealthStatus, { stroke: string; bg: string }> = {
  good: { stroke: '#C5FF35', bg: 'rgba(197, 255, 53, 0.15)' },      // Lime green
  warning: { stroke: '#FFD6F0', bg: 'rgba(255, 214, 240, 0.25)' },  // Pink
  critical: { stroke: '#FF6B6B', bg: 'rgba(255, 107, 107, 0.15)' }, // Red
};

const STATUS_LABELS: Record<RingMetric, string> = {
  runway: 'RUNWAY',
  liquidity: 'LIQUIDITY',
  cash_velocity: 'CASH VELOCITY',
};

// ============================================================================
// Component
// ============================================================================

export function HealthRing({
  metric,
  data,
  size = 'lg',
  animate = true,
  onClick,
  className,
}: HealthRingProps) {
  const [animatedPercentage, setAnimatedPercentage] = useState(animate ? 0 : data.percentage);

  // Animate ring fill on mount
  useEffect(() => {
    if (!animate) {
      setAnimatedPercentage(data.percentage);
      return;
    }

    // Small delay before animation starts
    const timeout = setTimeout(() => {
      setAnimatedPercentage(data.percentage);
    }, 100);

    return () => clearTimeout(timeout);
  }, [data.percentage, animate]);

  const sizeConfig = RING_SIZES[size];
  const colorConfig = STATUS_COLORS[data.status];

  // SVG calculations - radius accounts for stroke width to prevent clipping
  const viewBox = 100;
  const center = viewBox / 2;
  // Calculate radius so stroke stays within viewBox: radius + strokeWidth/2 <= center
  const radius = center - sizeConfig.strokeWidth / 2 - 1; // 1 unit padding
  const circumference = 2 * Math.PI * radius;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference - (animatedPercentage / 100) * circumference;

  return (
    <div
      className={cn(
        'flex flex-col items-center gap-2',
        onClick && 'cursor-pointer group',
        className
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {/* Ring SVG */}
      <div
        className={cn(
          'relative',
          onClick && 'transition-transform duration-200 group-hover:scale-105'
        )}
        style={{ width: sizeConfig.container, height: sizeConfig.container }}
      >
        <svg
          viewBox={`0 0 ${viewBox} ${viewBox}`}
          className="w-full h-full transform -rotate-90"
        >
          {/* Background ring */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={colorConfig.bg}
            strokeWidth={sizeConfig.strokeWidth}
          />
          {/* Progress ring */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={colorConfig.stroke}
            strokeWidth={sizeConfig.strokeWidth}
            strokeLinecap="round"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            className="transition-[stroke-dashoffset] duration-700 ease-out"
          />
        </svg>

        {/* Center value */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className="font-bold text-gunmetal"
            style={{ fontSize: sizeConfig.fontSize }}
          >
            {data.label}
          </span>
        </div>
      </div>

      {/* Label and sublabel */}
      <div className="flex flex-col items-center gap-0.5">
        <span
          className={cn(
            'font-semibold tracking-wider text-gunmetal uppercase flex items-center gap-1',
            onClick && 'group-hover:text-gunmetal/80'
          )}
          style={{ fontSize: sizeConfig.labelSize }}
        >
          {STATUS_LABELS[metric]}
          {onClick && (
            <svg
              className="inline-block opacity-60 group-hover:opacity-100 transition-opacity"
              width={sizeConfig.labelSize}
              height={sizeConfig.labelSize}
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <circle cx="8" cy="8" r="6.5" />
              <path d="M8 7v4" strokeLinecap="round" />
              <circle cx="8" cy="5" r="0.75" fill="currentColor" stroke="none" />
            </svg>
          )}
        </span>
        <span
          className="text-muted-foreground text-center"
          style={{ fontSize: sizeConfig.labelSize - 2 }}
        >
          {data.sublabel}
        </span>
      </div>
    </div>
  );
}

export default HealthRing;
