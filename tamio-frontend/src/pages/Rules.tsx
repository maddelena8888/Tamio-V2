import { RulesProvider, useRules } from '@/contexts/RulesContext';
import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { Skeleton } from '@/components/ui/skeleton';
import { RulesHeader } from '@/components/rules/RulesHeader';
import { RulesFilterTabs } from '@/components/rules/RulesFilterTabs';
import { RulesList } from '@/components/rules/RulesList';
import { RuleEmptyState } from '@/components/rules/RuleEmptyState';
import { CreateRuleSheet } from '@/components/rules/CreateRuleSheet';

function RulesContent() {
  const { rules, isLoading, filterCounts } = useRules();

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'rules',
    pageData: {
      totalRules: rules.length,
      activeRules: filterCounts.active,
      triggeredToday: filterCounts.triggered_today,
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-12 w-96" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <RulesHeader />
      <RulesFilterTabs />
      {rules.length === 0 ? <RuleEmptyState /> : <RulesList />}
      <CreateRuleSheet />
    </div>
  );
}

export default function Rules() {
  return (
    <RulesProvider>
      <RulesContent />
    </RulesProvider>
  );
}
