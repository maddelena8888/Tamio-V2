import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import type { ScenarioView } from './types';

interface ScenarioToggleProps {
  value: ScenarioView;
  onChange: (view: ScenarioView) => void;
}

export function ScenarioToggle({ value, onChange }: ScenarioToggleProps) {
  return (
    <Tabs value={value} onValueChange={(v) => onChange(v as ScenarioView)}>
      <TabsList className="bg-muted/50">
        <TabsTrigger
          value="expected"
          className={cn(
            'data-[state=active]:bg-white data-[state=active]:text-gunmetal'
          )}
        >
          Expected
        </TabsTrigger>
        <TabsTrigger
          value="bestCase"
          className={cn(
            'data-[state=active]:bg-lime/20 data-[state=active]:text-lime-dark'
          )}
        >
          Best Case
        </TabsTrigger>
        <TabsTrigger
          value="worstCase"
          className={cn(
            'data-[state=active]:bg-tomato/20 data-[state=active]:text-tomato'
          )}
        >
          Worst Case
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
