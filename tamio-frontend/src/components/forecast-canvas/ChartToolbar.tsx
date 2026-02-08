import { Activity, MessageSquare, Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { LayerToggle, TimeRange } from '@/pages/ForecastCanvas';
import { ScenarioDropdown, type ScenarioItem } from './ScenarioDropdown';
import type { ManualScenarioParams } from '@/components/scenarios';

interface AppliedScenario {
  id: string;
  name: string;
}

interface ChartToolbarProps {
  activeLayers: Set<LayerToggle>;
  toggleLayer: (layer: LayerToggle) => void;
  timeRange: TimeRange;
  changeTimeRange: (range: TimeRange) => void;
  appliedScenarios?: AppliedScenario[];
  savedScenarios?: ScenarioItem[];
  suggestedScenarios?: ScenarioItem[];
  teamScenarios?: ScenarioItem[];
  onScenarioSelect?: (scenario: { id: string; name: string }) => void;
  onScenarioRemove?: (scenarioId: string) => void;
  onScenarioBuild?: (params: ManualScenarioParams) => void;
}

// Scenario Chip component
function ScenarioChip({
  scenario,
  onRemove
}: {
  scenario: AppliedScenario;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-lime/20 border border-lime/30 rounded-full text-xs font-medium text-gunmetal animate-in fade-in-0 slide-in-from-left-2 duration-200">
      <span className="max-w-[120px] truncate">{scenario.name}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove(scenario.id);
        }}
        className="w-4 h-4 rounded-full hover:bg-gunmetal/10 flex items-center justify-center transition-colors"
        aria-label={`Remove ${scenario.name} scenario`}
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}

export function ChartToolbar({
  activeLayers,
  toggleLayer,
  timeRange,
  changeTimeRange,
  appliedScenarios = [],
  savedScenarios,
  suggestedScenarios,
  teamScenarios,
  onScenarioSelect,
  onScenarioRemove,
  onScenarioBuild,
}: ChartToolbarProps) {
  const timeRanges: TimeRange[] = ['13w', '26w', '52w'];

  const layers: { id: LayerToggle; label: string; icon: React.ReactNode }[] = [
    { id: 'confidence', label: 'Confidence', icon: <Activity className="w-3.5 h-3.5" /> },
    { id: 'comments', label: 'Comments', icon: <MessageSquare className="w-3.5 h-3.5" /> },
    { id: 'ai', label: 'Insights', icon: <Sparkles className="w-3.5 h-3.5" /> },
  ];

  const hasActiveScenarios = appliedScenarios.length > 0;

  return (
    <div className="flex items-center px-4 py-2 bg-white/30 backdrop-blur-sm border-b border-white/20 rounded-t-xl">
      <div className="flex items-center gap-4 flex-wrap">
        {/* Time Range Selector */}
        <div className="flex bg-white/50 rounded-lg p-0.5 border border-white/20">
          {timeRanges.map((range) => (
            <button
              key={range}
              onClick={() => changeTimeRange(range)}
              className={cn(
                'px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer transition-all border-none',
                timeRange === range
                  ? 'bg-gunmetal text-white shadow-sm'
                  : 'bg-transparent text-muted-foreground hover:text-gunmetal'
              )}
            >
              {range}
            </button>
          ))}
        </div>

        {/* Layer Toggles */}
        <div className="flex items-center gap-1.5 pl-4 border-l border-border/50">
          {layers.map((layer) => (
            <Button
              key={layer.id}
              variant={activeLayers.has(layer.id) ? 'default' : 'outline'}
              size="sm"
              onClick={() => toggleLayer(layer.id)}
              className={cn(
                'flex items-center gap-1.5 h-7 text-[11px]',
                activeLayers.has(layer.id)
                  ? 'bg-gunmetal hover:bg-gunmetal/90 text-white'
                  : 'bg-white/50 hover:bg-white border-white/30'
              )}
            >
              {layer.icon}
              {layer.label}
            </Button>
          ))}

          {/* Scenarios Dropdown */}
          <ScenarioDropdown
            isActive={hasActiveScenarios}
            activeCount={appliedScenarios.length}
            savedScenarios={savedScenarios}
            suggestedScenarios={suggestedScenarios}
            teamScenarios={teamScenarios}
            onScenarioSelect={onScenarioSelect}
            onScenarioBuild={onScenarioBuild}
          />
        </div>

        {/* Applied Scenario Chips */}
        {hasActiveScenarios && onScenarioRemove && (
          <div className="flex items-center gap-2 pl-4 border-l border-border/50">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Active:
            </span>
            {appliedScenarios.map((scenario) => (
              <ScenarioChip
                key={scenario.id}
                scenario={scenario}
                onRemove={onScenarioRemove}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
