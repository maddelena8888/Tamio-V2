import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { useRules } from '@/contexts/RulesContext';
import type { RulesFilter } from '@/lib/api/rules';

export function RulesFilterTabs() {
  const { activeFilter, setActiveFilter, filterCounts } = useRules();

  return (
    <Tabs
      value={activeFilter}
      onValueChange={(value) => setActiveFilter(value as RulesFilter)}
    >
      <TabsList className="bg-white/40 backdrop-blur-md">
        <TabsTrigger value="all" className="gap-2">
          All Rules
          <Badge variant="secondary" className="ml-1">
            {filterCounts.all}
          </Badge>
        </TabsTrigger>
        <TabsTrigger value="active" className="gap-2">
          Active
          <Badge variant="secondary" className="ml-1 bg-lime/20 text-lime-dark">
            {filterCounts.active}
          </Badge>
        </TabsTrigger>
        <TabsTrigger value="triggered_today" className="gap-2">
          Triggered Today
          <Badge variant="secondary" className="ml-1">
            {filterCounts.triggered_today}
          </Badge>
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
