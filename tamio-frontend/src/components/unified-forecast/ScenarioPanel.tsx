import { useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Sparkles,
  BookmarkCheck,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { ScenarioSuggestion, Scenario } from '@/lib/api/types';
import { useUnifiedForecastContext } from './UnifiedForecastContext';
import {
  SuggestedScenarioCard,
  SavedScenarioCard,
  ActiveScenarioBadge,
} from './ScenarioCard';

// ============================================================================
// Types
// ============================================================================

interface ScenarioPanelProps {
  suggestions: ScenarioSuggestion[];
  savedScenarios: Scenario[];
  isLoading?: boolean;
  loadingScenarioId?: string | null;
  onRunSuggested: (suggestion: ScenarioSuggestion) => void;
  onApplySaved: (scenario: Scenario) => void;
  onDeleteScenario?: (scenarioId: string) => void;
  onCreateNew: () => void;
  className?: string;
}

// ============================================================================
// Desktop Panel Component
// ============================================================================

export function ScenarioPanel({
  suggestions,
  savedScenarios,
  isLoading = false,
  loadingScenarioId = null,
  onRunSuggested,
  onApplySaved,
  onDeleteScenario,
  onCreateNew,
  className,
}: ScenarioPanelProps) {
  const { appliedScenarios, removeScenario, isPanelCollapsed, togglePanel } =
    useUnifiedForecastContext();

  const [suggestedOpen, setSuggestedOpen] = useState(true);
  const [savedOpen, setSavedOpen] = useState(savedScenarios.length > 0);

  // Check if scenario is active
  const isScenarioActive = (id: string) => appliedScenarios.some(s => s.id === id);
  const getScenarioColor = (id: string) => appliedScenarios.find(s => s.id === id)?.color;

  if (isPanelCollapsed) {
    return (
      <div className={cn('flex flex-col items-center py-4', className)}>
        <Button
          variant="ghost"
          size="icon"
          onClick={togglePanel}
          className="mb-4"
          title="Expand scenarios panel"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>

        {/* Active scenarios count badge */}
        {appliedScenarios.length > 0 && (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-lime/20 flex items-center justify-center">
              <span className="text-sm font-semibold text-lime-dark">
                {appliedScenarios.length}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground text-center">Active</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full overflow-hidden', className)}>
      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {/* Active Scenarios */}
        {appliedScenarios.length > 0 && (
          <div className="space-y-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Active ({appliedScenarios.length}/5)
            </span>
            <div className="flex flex-wrap gap-1.5">
              {appliedScenarios.map(scenario => (
                <ActiveScenarioBadge
                  key={scenario.id}
                  name={scenario.name}
                  color={scenario.color}
                  onRemove={() => removeScenario(scenario.id)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Suggested Scenarios */}
        <Collapsible open={suggestedOpen} onOpenChange={setSuggestedOpen}>
          <CollapsibleTrigger asChild>
            <button className="flex items-center justify-between w-full py-2 group">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                Suggested Scenarios
                {suggestions.length > 0 && (
                  <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">
                    {suggestions.length}
                  </span>
                )}
              </span>
              <ChevronRight
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  suggestedOpen && 'rotate-90'
                )}
              />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            {isLoading ? (
              <div className="grid grid-cols-3 gap-3">
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : suggestions.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {suggestions.slice(0, 5).map((suggestion, index) => (
                  <SuggestedScenarioCard
                    key={`${suggestion.scenario_type}-${index}`}
                    suggestion={suggestion}
                    isActive={false} // Suggestions don't have IDs yet
                    isLoading={loadingScenarioId === `suggestion-${index}`}
                    onRun={() => onRunSuggested(suggestion)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No suggested scenarios available
              </p>
            )}
          </CollapsibleContent>
        </Collapsible>

        {/* Saved Scenarios */}
        <Collapsible open={savedOpen} onOpenChange={setSavedOpen}>
          <CollapsibleTrigger asChild>
            <button className="flex items-center justify-between w-full py-2 group">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                <BookmarkCheck className="h-3.5 w-3.5 text-lime-dark" />
                Saved Scenarios
                {savedScenarios.length > 0 && (
                  <span className="text-[10px] bg-lime/20 text-lime-dark px-1.5 py-0.5 rounded-full">
                    {savedScenarios.length}
                  </span>
                )}
              </span>
              <ChevronRight
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  savedOpen && 'rotate-90'
                )}
              />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            {savedScenarios.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {savedScenarios.map(scenario => (
                  <SavedScenarioCard
                    key={scenario.id}
                    scenario={scenario}
                    isActive={isScenarioActive(scenario.id)}
                    color={getScenarioColor(scenario.id)}
                    isLoading={loadingScenarioId === scenario.id}
                    onApply={() => onApplySaved(scenario)}
                    onDelete={onDeleteScenario ? () => onDeleteScenario(scenario.id) : undefined}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No saved scenarios yet
              </p>
            )}
          </CollapsibleContent>
        </Collapsible>
      </div>

      {/* Footer: Create New */}
      <div className="px-4 py-3">
        <Button onClick={onCreateNew} className="w-full bg-gunmetal hover:bg-gunmetal/90">
          <Plus className="h-4 w-4 mr-2" />
          Create New Scenario
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Mobile Drawer Component
// ============================================================================

interface MobileScenarioDrawerProps extends ScenarioPanelProps {
  trigger?: React.ReactNode;
}

export function MobileScenarioDrawer({
  trigger,
  suggestions,
  savedScenarios,
  isLoading,
  loadingScenarioId,
  onRunSuggested,
  onApplySaved,
  onDeleteScenario,
  onCreateNew,
}: MobileScenarioDrawerProps) {
  const [open, setOpen] = useState(false);
  const { appliedScenarios } = useUnifiedForecastContext();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className="relative">
            <Layers className="h-4 w-4 mr-2" />
            Scenarios
            {appliedScenarios.length > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-lime text-gunmetal text-xs font-bold rounded-full flex items-center justify-center">
                {appliedScenarios.length}
              </span>
            )}
          </Button>
        )}
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:w-[400px] p-0">
        <SheetHeader className="px-4 py-3 border-b">
          <SheetTitle className="flex items-center gap-2 text-base">
            <Layers className="h-4 w-4" />
            Scenarios
          </SheetTitle>
        </SheetHeader>
        <ScenarioPanel
          suggestions={suggestions}
          savedScenarios={savedScenarios}
          isLoading={isLoading}
          loadingScenarioId={loadingScenarioId}
          onRunSuggested={suggestion => {
            onRunSuggested(suggestion);
            // Don't close on run - user might want to run multiple
          }}
          onApplySaved={scenario => {
            onApplySaved(scenario);
          }}
          onDeleteScenario={onDeleteScenario}
          onCreateNew={() => {
            onCreateNew();
            setOpen(false);
          }}
          className="h-[calc(100vh-60px)]"
        />
      </SheetContent>
    </Sheet>
  );
}

// ============================================================================
// Skeleton Component
// ============================================================================

function SkeletonCard() {
  return (
    <NeuroCard className="p-3">
      <Skeleton className="h-5 w-20 rounded-full" />
      <Skeleton className="h-4 w-3/4 mt-2" />
      <Skeleton className="h-3 w-full mt-1" />
      <Skeleton className="h-4 w-16 mt-2" />
      <Skeleton className="h-8 w-full mt-3" />
    </NeuroCard>
  );
}
