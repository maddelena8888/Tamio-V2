import { useState } from 'react';
import { Layers, Plus, Sparkles, Bookmark, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import { NeuroCard } from '@/components/ui/neuro-card';
import { cn } from '@/lib/utils';
import { ManualMode, type ManualScenarioParams } from '@/components/scenarios';

// Export ScenarioItem for use by parent components
export interface ScenarioItem {
  id: string;
  name: string;
  description?: string;
}

// Empty arrays as defaults when no data is passed
const emptyScenarios: ScenarioItem[] = [];

interface ScenarioGroupProps {
  title: string;
  icon: React.ReactNode;
  scenarios: ScenarioItem[];
  onSelect: (scenario: ScenarioItem) => void;
}

function ScenarioGroup({ title, icon, scenarios, onSelect }: ScenarioGroupProps) {
  if (scenarios.length === 0) return null;

  return (
    <div className="mb-3">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground mb-2 px-1">
        {icon}
        <span>{title}</span>
      </div>
      <div className="space-y-1">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            onClick={() => onSelect(scenario)}
            className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/50 transition-colors group"
          >
            <div className="text-sm font-medium text-gunmetal group-hover:text-gunmetal/90">
              {scenario.name}
            </div>
            {scenario.description && (
              <div className="text-[11px] text-muted-foreground">
                {scenario.description}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

interface ScenarioDropdownProps {
  isActive: boolean;
  activeCount?: number;
  savedScenarios?: ScenarioItem[];
  suggestedScenarios?: ScenarioItem[];
  teamScenarios?: ScenarioItem[];
  onScenarioSelect?: (scenario: ScenarioItem) => void;
  onScenarioBuild?: (params: ManualScenarioParams) => void;
}

export function ScenarioDropdown({
  isActive,
  activeCount = 0,
  savedScenarios = emptyScenarios,
  suggestedScenarios = emptyScenarios,
  teamScenarios = emptyScenarios,
  onScenarioSelect,
  onScenarioBuild,
}: ScenarioDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showBuildDialog, setShowBuildDialog] = useState(false);

  const handleScenarioSelect = (scenario: ScenarioItem) => {
    onScenarioSelect?.(scenario);
    setIsOpen(false);
  };

  const handleBuildNew = () => {
    setIsOpen(false);
    setShowBuildDialog(true);
  };

  const handleBuildScenario = (params: ManualScenarioParams) => {
    onScenarioBuild?.(params);
    setShowBuildDialog(false);
  };

  const handleCancelBuild = () => {
    setShowBuildDialog(false);
  };

  return (
    <>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button
            variant={isActive ? 'default' : 'outline'}
            size="sm"
            className={cn(
              'flex items-center gap-1.5 h-7 text-[11px] relative',
              isActive
                ? 'bg-gunmetal hover:bg-gunmetal/90 text-white'
                : 'bg-white/50 hover:bg-white border-white/30'
            )}
          >
            <Layers className="w-3.5 h-3.5" />
            Scenarios
            {/* Active indicator dot */}
            {isActive && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-lime rounded-full border-2 border-white shadow-sm" />
            )}
            {/* Badge count */}
            {activeCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 bg-lime text-gunmetal rounded-full text-[9px] font-bold min-w-[16px] text-center">
                {activeCount}
              </span>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-80 p-0 bg-white/95 backdrop-blur-sm border-gunmetal/10"
        >
          <div className="p-3 max-h-[400px] overflow-y-auto">
            <ScenarioGroup
              title="Tamio Recommended"
              icon={<Sparkles className="w-3 h-3" />}
              scenarios={suggestedScenarios}
              onSelect={handleScenarioSelect}
            />
            <ScenarioGroup
              title="Your Saved"
              icon={<Bookmark className="w-3 h-3" />}
              scenarios={savedScenarios}
              onSelect={handleScenarioSelect}
            />
            <ScenarioGroup
              title="Team Activity"
              icon={<Users className="w-3 h-3" />}
              scenarios={teamScenarios}
              onSelect={handleScenarioSelect}
            />

            {/* Empty state when no scenarios available */}
            {savedScenarios.length === 0 && suggestedScenarios.length === 0 && teamScenarios.length === 0 && (
              <div className="text-center py-6 text-muted-foreground">
                <p className="text-sm">No scenarios available</p>
                <p className="text-xs mt-1">Build a new scenario below</p>
              </div>
            )}
          </div>

          {/* Build New Scenario Button */}
          <div className="border-t border-gunmetal/10 p-2">
            <button
              onClick={handleBuildNew}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-gunmetal/5 hover:bg-gunmetal/10 text-gunmetal font-medium text-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              Build New Scenario
            </button>
          </div>
        </PopoverContent>
      </Popover>

      {/* Build Scenario Dialog */}
      <Dialog open={showBuildDialog} onOpenChange={setShowBuildDialog}>
        <DialogContent className="sm:max-w-[700px] p-0 overflow-hidden">
          <NeuroCard className="p-6 m-0 border-0 shadow-none">
            <ManualMode onBuild={handleBuildScenario} onCancel={handleCancelBuild} />
          </NeuroCard>
        </DialogContent>
      </Dialog>
    </>
  );
}
