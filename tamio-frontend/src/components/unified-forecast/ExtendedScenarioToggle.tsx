import { X } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import type { ScenarioView } from '@/components/projections/types';
import { useUnifiedForecastContext, type AppliedScenario } from './UnifiedForecastContext';

// ============================================================================
// Types
// ============================================================================

type ExtendedView = ScenarioView | `scenario-${string}`;

interface ExtendedScenarioToggleProps {
  className?: string;
  onRemoveScenario?: (scenarioId: string) => void;
}

// ============================================================================
// Component
// ============================================================================

export function ExtendedScenarioToggle({
  className,
  onRemoveScenario,
}: ExtendedScenarioToggleProps) {
  const { scenarioView, setScenarioView, appliedScenarios, removeScenario } =
    useUnifiedForecastContext();

  // Build current value for tabs - use base view or first applied scenario
  const currentValue: ExtendedView = scenarioView;

  const handleValueChange = (value: string) => {
    if (value.startsWith('scenario-')) {
      // When a scenario tab is selected, we keep the base view but highlight the scenario
      // The table will show the scenario data
      // For now, just stay on expected view
      setScenarioView('expected');
    } else {
      setScenarioView(value as ScenarioView);
    }
  };

  const handleRemoveScenario = (e: React.MouseEvent, scenarioId: string) => {
    e.stopPropagation();
    removeScenario(scenarioId);
    onRemoveScenario?.(scenarioId);
  };

  return (
    <Tabs value={currentValue} onValueChange={handleValueChange} className={className}>
      <TabsList className="bg-muted/50 h-auto flex-wrap gap-1 p-1">
        {/* Base scenario views */}
        <TabsTrigger
          value="expected"
          className={cn('data-[state=active]:bg-white data-[state=active]:text-gunmetal')}
        >
          Expected
        </TabsTrigger>
        <TabsTrigger
          value="bestCase"
          className={cn('data-[state=active]:bg-lime/20 data-[state=active]:text-lime-dark')}
        >
          Best Case
        </TabsTrigger>
        <TabsTrigger
          value="worstCase"
          className={cn('data-[state=active]:bg-tomato/20 data-[state=active]:text-tomato')}
        >
          Worst Case
        </TabsTrigger>

        {/* Custom scenario tabs */}
        {appliedScenarios.length > 0 && (
          <>
            {/* Separator */}
            <div className="h-6 w-px bg-gray-300 mx-1" />

            {appliedScenarios.map(scenario => (
              <ScenarioTab
                key={scenario.id}
                scenario={scenario}
                onRemove={e => handleRemoveScenario(e, scenario.id)}
              />
            ))}
          </>
        )}
      </TabsList>
    </Tabs>
  );
}

// ============================================================================
// ScenarioTab Component
// ============================================================================

interface ScenarioTabProps {
  scenario: AppliedScenario;
  onRemove: (e: React.MouseEvent) => void;
}

function ScenarioTab({ scenario, onRemove }: ScenarioTabProps) {
  return (
    <TabsTrigger
      value={`scenario-${scenario.id}`}
      className={cn(
        'relative pr-7 group',
        'data-[state=active]:text-white',
        'hover:bg-opacity-30'
      )}
      style={{
        backgroundColor: `${scenario.color}20`,
        borderColor: `${scenario.color}40`,
      }}
    >
      {/* Color dot */}
      <span
        className="w-2 h-2 rounded-full mr-1.5 flex-shrink-0"
        style={{ backgroundColor: scenario.color }}
      />

      {/* Name (truncated) */}
      <span className="max-w-[100px] truncate">{scenario.name}</span>

      {/* Remove button */}
      <button
        type="button"
        onClick={onRemove}
        className={cn(
          'absolute right-1 top-1/2 -translate-y-1/2',
          'p-0.5 rounded-full',
          'opacity-60 hover:opacity-100',
          'hover:bg-black/10 transition-opacity'
        )}
        title="Remove scenario"
      >
        <X className="h-3 w-3" />
      </button>
    </TabsTrigger>
  );
}

// ============================================================================
// Compact version for mobile
// ============================================================================

interface CompactScenarioToggleProps {
  className?: string;
}

export function CompactScenarioToggle({ className }: CompactScenarioToggleProps) {
  const { scenarioView, setScenarioView, appliedScenarios } = useUnifiedForecastContext();

  return (
    <div className={cn('flex items-center gap-2 flex-wrap', className)}>
      {/* Base view selector */}
      <select
        value={scenarioView}
        onChange={e => setScenarioView(e.target.value as ScenarioView)}
        className="h-9 px-3 rounded-md border border-input bg-background text-sm"
      >
        <option value="expected">Expected</option>
        <option value="bestCase">Best Case</option>
        <option value="worstCase">Worst Case</option>
      </select>

      {/* Applied scenarios badges */}
      {appliedScenarios.length > 0 && (
        <div className="flex items-center gap-1">
          {appliedScenarios.map(scenario => (
            <span
              key={scenario.id}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium"
              style={{
                backgroundColor: `${scenario.color}20`,
                color: scenario.color,
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: scenario.color }}
              />
              {scenario.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
