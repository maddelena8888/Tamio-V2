import { Check, Play, Trash2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NeuroCard } from '@/components/ui/neuro-card';
import { cn } from '@/lib/utils';
import type { ScenarioSuggestion, Scenario } from '@/lib/api/types';

// ============================================================================
// Priority/Risk Styles
// ============================================================================

function getPriorityStyles(priority: 'high' | 'medium' | 'low') {
  switch (priority) {
    case 'high':
      return {
        badge: 'bg-tomato/10 text-tomato border-tomato/20',
        label: 'HIGH RISK',
      };
    case 'medium':
      return {
        badge: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
        label: 'MEDIUM RISK',
      };
    case 'low':
      return {
        badge: 'bg-lime-dark/10 text-lime-dark border-lime-dark/20',
        label: 'LOW RISK',
      };
  }
}

// ============================================================================
// SuggestedScenarioCard Component
// ============================================================================

interface SuggestedScenarioCardProps {
  suggestion: ScenarioSuggestion;
  isActive?: boolean;
  isLoading?: boolean;
  onRun: () => void;
  className?: string;
}

export function SuggestedScenarioCard({
  suggestion,
  isActive = false,
  isLoading = false,
  onRun,
  className,
}: SuggestedScenarioCardProps) {
  const priorityStyles = getPriorityStyles(suggestion.priority);

  return (
    <NeuroCard
      className={cn(
        'p-3 flex flex-col transition-all',
        isActive && 'ring-2 ring-lime ring-offset-2',
        !isActive && 'hover:shadow-lg',
        className
      )}
    >
      {/* Priority Badge */}
      <div
        className={cn(
          'inline-flex items-center self-start px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider border',
          priorityStyles.badge
        )}
      >
        {isActive && <Check className="h-3 w-3 mr-1" />}
        {priorityStyles.label}
      </div>

      {/* Scenario Name */}
      <h4 className="text-sm font-semibold text-gunmetal mt-2 line-clamp-2">{suggestion.name}</h4>

      {/* Description */}
      <p className="text-xs text-muted-foreground mt-1 line-clamp-2 flex-1">
        {suggestion.description}
      </p>

      {/* Buffer Impact */}
      {suggestion.buffer_impact && (
        <div className="mt-2">
          <span
            className={cn(
              'text-sm font-semibold',
              suggestion.buffer_impact.startsWith('-') ? 'text-tomato' : 'text-lime-dark'
            )}
          >
            {suggestion.buffer_impact}
          </span>
        </div>
      )}

      {/* Run Button */}
      <Button
        onClick={onRun}
        disabled={isLoading || isActive}
        size="sm"
        className={cn(
          'mt-3 w-full',
          isActive
            ? 'bg-lime/20 text-lime-dark hover:bg-lime/30'
            : 'bg-gunmetal hover:bg-gunmetal/90 text-white'
        )}
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            Running...
          </>
        ) : isActive ? (
          <>
            <Check className="h-4 w-4 mr-1.5" />
            Applied
          </>
        ) : (
          <>
            <Play className="h-4 w-4 mr-1.5" />
            Run Scenario
          </>
        )}
      </Button>
    </NeuroCard>
  );
}

// ============================================================================
// SavedScenarioCard Component
// ============================================================================

interface SavedScenarioCardProps {
  scenario: Scenario;
  isActive?: boolean;
  color?: string;
  isLoading?: boolean;
  onApply: () => void;
  onDelete?: () => void;
  className?: string;
}

export function SavedScenarioCard({
  scenario,
  isActive = false,
  color,
  isLoading = false,
  onApply,
  onDelete,
  className,
}: SavedScenarioCardProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between p-3 rounded-lg border transition-all',
        isActive
          ? 'bg-white border-gray-200 shadow-sm'
          : 'bg-white/50 border-transparent hover:bg-white/80',
        className
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        {/* Color indicator (when active) */}
        {isActive && color && (
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
        )}

        {/* Name */}
        <span className={cn('text-sm font-medium truncate', isActive && 'text-gunmetal')}>
          {scenario.name}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {isActive ? (
          <Button variant="ghost" size="sm" onClick={onApply} className="h-7 px-2">
            <Check className="h-3.5 w-3.5 text-lime-dark" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            onClick={onApply}
            disabled={isLoading}
            className="h-7 px-2 text-muted-foreground hover:text-gunmetal"
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
          </Button>
        )}

        {onDelete && !isActive && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onDelete}
            className="h-7 px-2 text-muted-foreground hover:text-tomato"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// ActiveScenarioBadge Component (for showing in panel)
// ============================================================================

interface ActiveScenarioBadgeProps {
  name: string;
  color: string;
  onRemove: () => void;
}

export function ActiveScenarioBadge({ name, color, onRemove }: ActiveScenarioBadgeProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
        'border cursor-pointer hover:opacity-80 transition-opacity'
      )}
      style={{
        backgroundColor: `${color}15`,
        borderColor: `${color}30`,
        color: color,
      }}
      onClick={onRemove}
      title="Click to remove"
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
      <span className="max-w-[80px] truncate">{name}</span>
      <span className="text-[10px] opacity-60">×</span>
    </div>
  );
}
