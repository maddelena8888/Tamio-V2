import { useMemo } from 'react';
import { Gauge, Plus } from 'lucide-react';
import { RuleProgressCard, calculateRuleProgress } from '../cards/RuleProgressCard';
import { useNotificationCentre } from '../NotificationCentreContext';
import { useRules } from '@/contexts/RulesContext';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

function EmptyState() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
        <Gauge className="w-6 h-6 text-gray-400" />
      </div>
      <h3 className="text-sm font-semibold text-gunmetal mb-1">No rules set up</h3>
      <p className="text-xs text-muted-foreground max-w-[250px] mb-4">
        Create financial safety rules to monitor your cash flow and get alerts when thresholds are approached.
      </p>
      <Button
        size="sm"
        onClick={() => navigate('/rules')}
        className="gap-1.5"
      >
        <Plus className="w-4 h-4" />
        Create a Rule
      </Button>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <div key={i} className="p-3 rounded-xl border border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Skeleton className="w-8 h-8 rounded-lg" />
              <Skeleton className="h-4 w-32" />
            </div>
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
          <Skeleton className="h-2.5 w-full rounded-full mb-1.5" />
          <div className="flex justify-between">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-3 w-10" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function RulesTab() {
  const { setUnreadCounts, unreadCounts } = useNotificationCentre();
  const { rules, isLoading } = useRules();

  // Calculate progress for each rule
  const ruleProgressList = useMemo(() => {
    return rules.map((rule) => calculateRuleProgress(rule));
  }, [rules]);

  // Count triggered/warning rules for badge
  useMemo(() => {
    const triggeredCount = ruleProgressList.filter(
      (rp) => rp.status === 'triggered' || rp.status === 'warning'
    ).length;

    if (triggeredCount !== unreadCounts.rules) {
      setUnreadCounts({
        ...unreadCounts,
        rules: triggeredCount,
      });
    }
  }, [ruleProgressList]);

  // Sort by status priority: triggered > warning > healthy > paused
  const sortedRuleProgress = useMemo(() => {
    const statusOrder: Record<string, number> = {
      triggered: 0,
      warning: 1,
      healthy: 2,
      paused: 3,
    };

    return [...ruleProgressList].sort(
      (a, b) => statusOrder[a.status] - statusOrder[b.status]
    );
  }, [ruleProgressList]);

  if (isLoading) {
    return <LoadingSkeleton />;
  }

  if (rules.length === 0) {
    return <EmptyState />;
  }

  // Group by status
  const triggeredRules = sortedRuleProgress.filter((rp) => rp.status === 'triggered');
  const warningRules = sortedRuleProgress.filter((rp) => rp.status === 'warning');
  const healthyRules = sortedRuleProgress.filter((rp) => rp.status === 'healthy');
  const pausedRules = sortedRuleProgress.filter((rp) => rp.status === 'paused');

  return (
    <div className="space-y-4">
      {/* Triggered Section */}
      {triggeredRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-tomato/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-tomato" />
              <span className="text-xs font-medium uppercase tracking-wide text-tomato">
                Triggered ({triggeredRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {triggeredRules.map((rp) => (
              <RuleProgressCard key={rp.rule.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}

      {/* Warning Section */}
      {warningRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-amber-500/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-amber-600">
                Warning ({warningRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {warningRules.map((rp) => (
              <RuleProgressCard key={rp.rule.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}

      {/* Healthy Section */}
      {healthyRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-lime/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-lime" />
              <span className="text-xs font-medium uppercase tracking-wide text-lime-700">
                Healthy ({healthyRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {healthyRules.map((rp) => (
              <RuleProgressCard key={rp.rule.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}

      {/* Paused Section */}
      {pausedRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-gray-100">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-gray-400" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Paused ({pausedRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {pausedRules.map((rp) => (
              <RuleProgressCard key={rp.rule.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
