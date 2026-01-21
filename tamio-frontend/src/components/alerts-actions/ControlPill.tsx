/**
 * ControlPill Component - V4 Risk/Controls Architecture
 *
 * Compact representation of a control in the horizontal rail.
 * Shows:
 * - State indicator (colored dot)
 * - Control name
 * - Linked risk count badge
 * - Visual "system control" feel (not a PM task card)
 */

import { cn } from '@/lib/utils';
import type { Control } from '@/lib/api/alertsActions';
import { getControlStateStyles } from '@/lib/api/alertsActions';
import { Shield, Clock, Check, AlertTriangle } from 'lucide-react';

interface ControlPillProps {
  control: Control;
  isHighlighted: boolean;
  isSelected: boolean;
  linkedRiskCount: number;
  linkedRiskName?: string;
  onClick: () => void;
}

export function ControlPill({
  control,
  isHighlighted,
  isSelected,
  linkedRiskCount: _linkedRiskCount, // Reserved for potential future use
  linkedRiskName,
  onClick,
}: ControlPillProps) {
  const stateStyles = getControlStateStyles(control.state);

  const StateIcon = {
    pending: Clock,
    active: Shield,
    completed: Check,
    needs_review: AlertTriangle,
  }[control.state];

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex flex-col gap-1 px-3 py-2 rounded-lg border transition-all duration-150',
        'flex-shrink-0 min-w-[200px] max-w-[280px] text-left',
        // Base styles - glassmorphic
        'bg-white/70 backdrop-blur-sm border-white/50',
        // State-based background tint
        stateStyles.bgClass,
        // Highlight when linked risk selected
        isHighlighted && 'ring-2 ring-lime ring-offset-1',
        // Selected state
        isSelected && 'ring-2 ring-gunmetal/50 ring-offset-1 shadow-md',
        // Hover
        !isHighlighted && !isSelected && 'hover:bg-white/90 hover:shadow-sm hover:border-gray-300'
      )}
    >
      {/* Top row: State indicator, icon, control name, state label */}
      <div className="flex items-center gap-2">
        {/* State indicator */}
        <div className={cn(
          'w-2 h-2 rounded-full flex-shrink-0',
          stateStyles.dotClass
        )} />

        {/* State icon */}
        <StateIcon className={cn('w-3.5 h-3.5 flex-shrink-0', stateStyles.textClass)} />

        {/* Control name */}
        <span className="text-sm font-medium text-gunmetal truncate flex-1">
          {control.name}
        </span>

        {/* State label */}
        <span className={cn(
          'text-xs font-medium px-1.5 py-0.5 rounded flex-shrink-0',
          stateStyles.bgClass,
          stateStyles.textClass
        )}>
          {control.state_label}
        </span>
      </div>

      {/* Bottom row: Linked risk name */}
      {linkedRiskName && (
        <div className="flex items-center gap-1.5 pl-4">
          <span className="text-[10px] text-gray-400 uppercase tracking-wide">Addresses:</span>
          <span className="text-xs text-gray-600 truncate">{linkedRiskName}</span>
        </div>
      )}
    </button>
  );
}

// ============================================================================
// Empty State
// ============================================================================

export function EmptyControlsState() {
  return (
    <div className="flex items-center justify-center py-6 px-4 text-center">
      <div className="flex items-center gap-3 text-gray-400">
        <Shield className="w-5 h-5" />
        <span className="text-sm">No active controls</span>
      </div>
    </div>
  );
}
