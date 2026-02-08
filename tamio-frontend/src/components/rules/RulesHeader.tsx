import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useRules } from '@/contexts/RulesContext';

export function RulesHeader() {
  const { openCreateSheet } = useRules();

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 className="font-league-spartan text-3xl font-bold text-gunmetal">
          Rules & Alerts
        </h1>
        <p className="text-muted-foreground mt-1">
          Set up automated monitoring for your business
        </p>
      </div>
      <Button onClick={openCreateSheet} className="rounded-full gap-2">
        <Plus className="h-4 w-4" />
        Create Rule
      </Button>
    </div>
  );
}
