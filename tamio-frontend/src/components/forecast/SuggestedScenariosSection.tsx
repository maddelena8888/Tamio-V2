import { Plus, Share } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { ScenarioSuggestion } from '@/lib/api/types';

interface SuggestedScenariosSectionProps {
  suggestions: ScenarioSuggestion[];
  isLoading: boolean;
  onRunSuggested: (suggestion: ScenarioSuggestion) => void;
  onAddNewScenario: () => void;
  onShare: () => void;
}

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

function SuggestedScenarioCard({
  suggestion,
  onRun,
}: {
  suggestion: ScenarioSuggestion;
  onRun: () => void;
}) {
  const priorityStyles = getPriorityStyles(suggestion.priority);

  return (
    <NeuroCard className="p-5 flex flex-col h-full hover:shadow-xl transition-shadow">
      {/* Priority Badge */}
      <div
        className={cn(
          'inline-flex items-center self-start px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider border',
          priorityStyles.badge
        )}
      >
        {priorityStyles.label}
      </div>

      {/* Scenario Name */}
      <h3 className="text-base font-semibold text-gunmetal mt-3 line-clamp-2">
        {suggestion.name}
      </h3>

      {/* Description */}
      <p className="text-sm text-muted-foreground mt-2 line-clamp-2 flex-1">
        {suggestion.description}
      </p>

      {/* Buffer Impact */}
      {suggestion.buffer_impact && (
        <div className="mt-3">
          <span
            className={cn(
              'text-sm font-medium',
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
        className="mt-4 w-full bg-gunmetal hover:bg-gunmetal/90 text-white"
        size="sm"
      >
        Run Scenario
      </Button>
    </NeuroCard>
  );
}

function SkeletonCard() {
  return (
    <NeuroCard className="p-5">
      <Skeleton className="h-6 w-24 rounded-full" />
      <Skeleton className="h-5 w-3/4 mt-3" />
      <Skeleton className="h-4 w-full mt-2" />
      <Skeleton className="h-4 w-2/3 mt-1" />
      <Skeleton className="h-4 w-20 mt-3" />
      <Skeleton className="h-9 w-full mt-4" />
    </NeuroCard>
  );
}

export function SuggestedScenariosSection({
  suggestions,
  isLoading,
  onRunSuggested,
  onAddNewScenario,
  onShare,
}: SuggestedScenariosSectionProps) {
  return (
    <div className="space-y-6">
      {/* Header with Actions */}
      <div className="flex items-center justify-between">
        <Button
          onClick={onAddNewScenario}
          variant="outline"
          className="flex items-center gap-2 border-gunmetal/20 hover:bg-white/50"
        >
          <Plus className="h-4 w-4" />
          Add New Scenario
        </Button>

        <Button
          onClick={onShare}
          className="flex items-center gap-2 bg-gunmetal hover:bg-gunmetal/90 text-white"
        >
          <Share className="h-4 w-4" />
          Share
        </Button>
      </div>

      {/* Suggested Scenarios Grid */}
      <div>
        <h2 className="text-lg font-semibold text-gunmetal mb-4">Suggested Scenarios</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {isLoading ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : suggestions.length > 0 ? (
            suggestions.slice(0, 3).map((suggestion, index) => (
              <SuggestedScenarioCard
                key={`${suggestion.scenario_type}-${index}`}
                suggestion={suggestion}
                onRun={() => onRunSuggested(suggestion)}
              />
            ))
          ) : (
            <div className="col-span-full">
              <NeuroCard className="p-8 text-center">
                <p className="text-muted-foreground">
                  No suggested scenarios available. Click "Add New Scenario" to create one manually.
                </p>
              </NeuroCard>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
