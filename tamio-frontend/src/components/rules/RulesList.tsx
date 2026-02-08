import { useRules } from '@/contexts/RulesContext';
import { RuleCard } from './RuleCard';

export function RulesList() {
  const { filteredRules } = useRules();

  if (filteredRules.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        No rules match the current filter.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {filteredRules.map((rule) => (
        <RuleCard key={rule.id} rule={rule} />
      ))}
    </div>
  );
}
