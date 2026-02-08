import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Check, Calendar, RefreshCw, CheckCircle, TrendingUp, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { NeuroCard } from '@/components/ui/neuro-card';
import { cn } from '@/lib/utils';
import { AlertDetailPopup, type CanvasAlert } from './AlertDetailPopup';
import type { SidebarTab, CanvasMetrics } from '@/pages/ForecastCanvas';
import type { FinancialRule } from '@/lib/api/types';
import { useAuth } from '@/contexts/AuthContext';
import {
  getRisks,
  getControls,
  type Risk,
  type Control,
  type DecisionItem,
  type RiskSeverity,
} from '@/lib/api/alertsActions';
import { buildDecisionQueue, formatAmount } from '@/lib/utils/decisionQueue';

interface RightSidebarProps {
  activeTab: SidebarTab;
  setActiveTab: (tab: SidebarTab) => void;
  rules: FinancialRule[];
  metrics: CanvasMetrics;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// Transform Risk/DecisionItem to CanvasAlert format for AlertDetailPopup
function riskToCanvasAlert(item: DecisionItem): CanvasAlert {
  const { alert, recommendation } = item;
  const context = (alert as { context_data?: Record<string, unknown> }).context_data || {};

  // Determine tier based on section
  const tier: 'act-now' | 'monitor' = item.section === 'requires_decision' ? 'act-now' : 'monitor';

  // Extract linked entity info
  let linkedEntity: CanvasAlert['linkedEntity'] = undefined;
  if (context.client_name) {
    linkedEntity = { type: 'client', name: context.client_name as string };
  } else if (context.payroll_amount || context.obligation_category === 'payroll') {
    linkedEntity = { type: 'payroll', name: 'Payroll' };
  } else if (context.obligation_type?.toString().toLowerCase().includes('tax')) {
    linkedEntity = { type: 'tax', name: context.obligation_name as string || 'Tax Payment' };
  } else if (context.vendor_name || context.bucket_name) {
    linkedEntity = { type: 'vendor', name: (context.vendor_name || context.bucket_name) as string };
  } else {
    // Try to extract from primary_driver
    const driver = alert.primary_driver || '';
    const clientMatch = driver.match(/^([A-Z][a-zA-Z\s]+(?:Inc|Co|LLC|Corp|Ltd)?)/);
    if (clientMatch) {
      linkedEntity = { type: 'client', name: clientMatch[1].trim() };
    }
  }

  // Generate recommended actions
  const recommendedActions: CanvasAlert['recommendedActions'] = [];
  if (recommendation) {
    const recName = recommendation.name.toLowerCase();
    let icon: 'email' | 'phone' | 'invoice' | 'transfer' | 'schedule' | 'review' = 'review';
    if (recName.includes('send') || recName.includes('reminder') || recName.includes('email')) {
      icon = 'email';
    } else if (recName.includes('call') || recName.includes('phone')) {
      icon = 'phone';
    } else if (recName.includes('invoice') || recName.includes('accelerate')) {
      icon = 'invoice';
    } else if (recName.includes('sweep') || recName.includes('transfer') || recName.includes('defer')) {
      icon = 'transfer';
    } else if (recName.includes('schedule')) {
      icon = 'schedule';
    }
    recommendedActions.push({
      icon,
      label: recommendation.name,
      description: recommendation.why_it_exists,
      primary: true,
    });
  } else {
    // Default actions based on alert type
    if (alert.title.toLowerCase().includes('overdue')) {
      recommendedActions.push({
        icon: 'email',
        label: 'Send payment reminder',
        description: 'Follow up on overdue payment',
        primary: true,
      });
    } else {
      recommendedActions.push({
        icon: 'review',
        label: 'Review and take action',
        description: 'Assess the situation',
        primary: true,
      });
    }
  }

  return {
    id: alert.id,
    tier,
    type: alert.title.toLowerCase().includes('overdue') ? 'overdue' : 'upcoming',
    title: alert.title,
    subtitle: alert.primary_driver || alert.due_horizon_label,
    body: alert.context_bullets.join(' ') || 'Review this alert and take appropriate action.',
    severity: alert.severity as 'urgent' | 'high' | 'normal',
    impact: alert.impact_statement || (alert.cash_impact ? `Impact: ${formatAmount(alert.cash_impact)} at risk` : undefined),
    dueDate: alert.due_horizon_label !== 'No deadline' ? alert.due_horizon_label : undefined,
    linkedEntity,
    recommendedActions,
  };
}

const mockActivity = [
  { id: '1', type: 'payment' as const, highlight: 'TechCorp', text: 'paid invoice INV-2024-087', time: '2 hours ago' },
  { id: '2', type: 'update' as const, highlight: 'Forecast', text: 'updated with new expense data', time: '5 hours ago' },
  { id: '3', type: 'complete' as const, highlight: 'Payroll', text: 'processed successfully', time: 'Yesterday' },
];

const mockDailySummary = [
  { type: 'positive' as const, text: 'Cash received', value: '+$24,500' },
  { type: 'negative' as const, text: 'Expenses paid', value: '-$8,200' },
  { type: 'neutral' as const, text: 'Runway change', value: '+0.5w' },
];

// Sidebar Tabs
function SidebarTabs({
  activeTab,
  setActiveTab,
  rules,
  totalAlerts,
}: {
  activeTab: SidebarTab;
  setActiveTab: (tab: SidebarTab) => void;
  rules: FinancialRule[];
  totalAlerts: number;
}) {
  const atRiskRules = rules.filter((r) => {
    // Simple check - would be more sophisticated in production
    return r.rule_type === 'minimum_cash_buffer';
  });

  const tabs: { id: SidebarTab; label: string; badge?: number; urgent?: boolean }[] = [
    { id: 'alerts', label: 'Alerts', badge: totalAlerts },
    { id: 'activity', label: 'Activity' },
    { id: 'rules', label: 'Rules', badge: atRiskRules.length > 0 ? 1 : 0, urgent: true },
  ];

  return (
    <div className="flex gap-0.5 bg-white/50 p-0.5 rounded-lg">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={cn(
            'flex-1 py-2 px-2 rounded-md text-xs font-medium cursor-pointer transition-all border-none text-center flex items-center justify-center gap-1.5',
            activeTab === tab.id
              ? 'bg-white text-gunmetal shadow-sm'
              : 'bg-transparent text-muted-foreground hover:text-gunmetal'
          )}
        >
          {tab.label}
          {tab.badge !== undefined && tab.badge > 0 && (
            <span
              className={cn(
                'text-[10px] font-semibold px-1.5 py-0.5 rounded-lg min-w-[18px] text-center',
                tab.urgent
                  ? 'bg-tomato text-white'
                  : 'bg-amber-100 text-amber-700'
              )}
            >
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// Daily Summary Card
function DailySummary() {
  return (
    <NeuroCard className="p-3 mb-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Since Yesterday
        </span>
        <span className="text-[10px] text-muted-foreground">Feb 3, 2026</span>
      </div>
      <div className="flex flex-col gap-2">
        {mockDailySummary.map((item, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <div
              className={cn(
                'w-5 h-5 rounded flex items-center justify-center',
                item.type === 'positive'
                  ? 'bg-lime/20 text-lime-dark'
                  : item.type === 'negative'
                  ? 'bg-tomato/10 text-tomato'
                  : 'bg-amber-50 text-amber-600'
              )}
            >
              {item.type === 'positive' ? (
                <Check className="w-3 h-3" />
              ) : item.type === 'negative' ? (
                <AlertCircle className="w-3 h-3" />
              ) : (
                <TrendingUp className="w-3 h-3" />
              )}
            </div>
            <span className="text-muted-foreground">{item.text}</span>
            <span className="font-semibold text-gunmetal ml-auto">
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </NeuroCard>
  );
}

const INITIAL_VISIBLE = 3;

// Alerts Panel - displays real data from API
function AlertsPanel({ decisionItems, isLoading }: { decisionItems: DecisionItem[]; isLoading: boolean }) {
  const [selectedAlert, setSelectedAlert] = useState<CanvasAlert | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);

  // Split items into Act Now (requires_decision) and Monitor (monitoring + being_handled)
  const actNowItems = useMemo(() =>
    decisionItems.filter((item) => item.section === 'requires_decision'),
    [decisionItems]
  );
  const monitorItems = useMemo(() =>
    decisionItems.filter((item) => item.section === 'monitoring' || item.section === 'being_handled'),
    [decisionItems]
  );

  // Progressive disclosure: limit visible items when collapsed
  const visibleActNowItems = isExpanded ? actNowItems : actNowItems.slice(0, INITIAL_VISIBLE);
  const hiddenCount = actNowItems.length - INITIAL_VISIBLE;

  const handleAlertClick = (item: DecisionItem) => {
    const canvasAlert = riskToCanvasAlert(item);
    setSelectedAlert(canvasAlert);
  };

  // Get glassmorphic background based on severity
  const getSeverityBackground = (severity: RiskSeverity) => {
    switch (severity) {
      case 'urgent': return 'bg-tomato/15 hover:bg-tomato/20';
      case 'high': return 'bg-amber-500/15 hover:bg-amber-500/20';
      default: return 'bg-lime/15 hover:bg-lime/20';
    }
  };

  // Get icon background based on severity
  const getIconStyles = (severity: RiskSeverity) => {
    switch (severity) {
      case 'urgent': return 'bg-white/60 text-tomato';
      case 'high': return 'bg-white/60 text-amber-600';
      default: return 'bg-white/60 text-lime-dark';
    }
  };

  if (isLoading) {
    return (
      <div className="p-3">
        <DailySummary />
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading alerts...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3">
      <DailySummary />

      {/* Empty state */}
      {decisionItems.length === 0 && (
        <div className="text-center py-8">
          <Check className="w-8 h-8 text-lime-dark mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No alerts at this time</p>
        </div>
      )}

      {/* Act Now Tier (requires_decision) */}
      {actNowItems.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            <span className="w-2 h-2 rounded-full bg-tomato" />
            Requires Decision ({actNowItems.length})
          </div>
          {visibleActNowItems.map((item) => (
            <div
              key={item.id}
              className={cn(
                'p-3 mb-2 rounded-xl cursor-pointer transition-all duration-200',
                'backdrop-blur-md border border-white/30',
                'shadow-[inset_0_1px_1px_rgba(255,255,255,0.6),0_2px_8px_rgba(0,0,0,0.06)]',
                'hover:shadow-[inset_0_1px_1px_rgba(255,255,255,0.8),0_4px_12px_rgba(0,0,0,0.1)]',
                getSeverityBackground(item.alert.severity)
              )}
              onClick={() => handleAlertClick(item)}
            >
              <div className="flex items-start gap-2 mb-2">
                <div className={cn(
                  'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0',
                  getIconStyles(item.alert.severity)
                )}>
                  <AlertCircle className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-gunmetal mb-0.5 truncate">
                    {item.alert.title}
                  </div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {item.alert.primary_driver || item.alert.due_horizon_label}
                  </div>
                </div>
              </div>
              {item.alert.impact_statement && (
                <div className="text-xs text-tomato/90 font-medium mb-1">
                  {item.alert.impact_statement}
                </div>
              )}
              <div className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                {item.alert.context_bullets[0] || 'Review this alert and take appropriate action.'}
              </div>
            </div>
          ))}
          {/* Expand/Collapse Button */}
          {hiddenCount > 0 && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="w-full flex items-center justify-center gap-1.5 py-2 text-xs text-muted-foreground hover:text-gunmetal hover:bg-white/30 rounded-lg transition-colors"
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="w-3.5 h-3.5" />
                  Show less
                </>
              ) : (
                <>
                  <ChevronDown className="w-3.5 h-3.5" />
                  Show {hiddenCount} more
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Divider */}
      {actNowItems.length > 0 && monitorItems.length > 0 && (
        <div className="h-px bg-border/50 my-3" />
      )}

      {/* Monitor Tier (monitoring + being_handled) */}
      {monitorItems.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            Monitoring ({monitorItems.length})
          </div>
          {monitorItems.map((item) => (
            <div
              key={item.id}
              className={cn(
                'p-3 mb-2 rounded-xl cursor-pointer transition-all duration-200',
                'backdrop-blur-md border border-white/30',
                'shadow-[inset_0_1px_1px_rgba(255,255,255,0.6),0_2px_8px_rgba(0,0,0,0.06)]',
                'hover:shadow-[inset_0_1px_1px_rgba(255,255,255,0.8),0_4px_12px_rgba(0,0,0,0.1)]',
                item.section === 'being_handled'
                  ? 'bg-blue-500/15 hover:bg-blue-500/20'
                  : 'bg-amber-500/15 hover:bg-amber-500/20'
              )}
              onClick={() => handleAlertClick(item)}
            >
              <div className="flex items-start gap-2 mb-2">
                <div className={cn(
                  'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0',
                  item.section === 'being_handled'
                    ? 'bg-white/60 text-blue-600'
                    : 'bg-white/60 text-amber-600'
                )}>
                  {item.section === 'being_handled' ? (
                    <RefreshCw className="w-4 h-4" />
                  ) : (
                    <Calendar className="w-4 h-4" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-gunmetal mb-0.5 truncate">
                    {item.alert.title}
                  </div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {item.section === 'being_handled' ? 'In progress' : item.alert.due_horizon_label}
                  </div>
                </div>
              </div>
              <div className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                {item.alert.context_bullets[0] || 'Monitoring this item.'}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Alert Detail Popup */}
      {selectedAlert && (
        <AlertDetailPopup
          alert={selectedAlert}
          isOpen={!!selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}
    </div>
  );
}

// Activity Panel
function ActivityPanel() {
  return (
    <div className="p-3">
      {mockActivity.map((item) => (
        <div
          key={item.id}
          className="flex gap-2 py-3 border-b border-border/30 last:border-b-0"
        >
          <div
            className={cn(
              'w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0',
              item.type === 'payment'
                ? 'bg-lime/20 text-lime-dark'
                : item.type === 'update'
                ? 'bg-blue-50 text-blue-600'
                : 'bg-amber-50 text-amber-600'
            )}
          >
            {item.type === 'payment' ? (
              <Check className="w-3.5 h-3.5" />
            ) : item.type === 'update' ? (
              <RefreshCw className="w-3.5 h-3.5" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5" />
            )}
          </div>
          <div>
            <div className="text-xs text-muted-foreground leading-relaxed">
              {item.highlight && (
                <strong className="text-gunmetal">{item.highlight}</strong>
              )}{' '}
              {item.text}
            </div>
            <div className="text-[10px] text-muted-foreground mt-1">{item.time}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// Rules Panel
function RulesPanel({ rules }: { rules: FinancialRule[] }) {
  const navigate = useNavigate();

  const handleRuleClick = () => {
    navigate('/scenarios');
  };

  // Display rules or fallback to default rule
  const displayRules = rules.length > 0 ? rules : [
    {
      id: 'default-buffer',
      rule_type: 'minimum_cash_buffer',
      threshold_config: { months: 3 },
    },
  ];

  return (
    <div className="p-3">
      {displayRules.map((rule) => {
        const isBufferRule = rule.rule_type === 'minimum_cash_buffer';
        const months = rule.threshold_config?.months || 3;

        return (
          <NeuroCard
            key={rule.id}
            className="p-3 mb-2 cursor-pointer hover:shadow-md transition-shadow"
            onClick={handleRuleClick}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] font-medium text-gunmetal">
                {isBufferRule ? 'Cash Buffer Rule' : rule.rule_type}
              </span>
              <span
                className={cn(
                  'px-2 py-0.5 rounded-xl text-[10px] font-semibold',
                  'bg-lime/20 text-lime-dark'
                )}
              >
                Active
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground">
              {isBufferRule
                ? `Maintain ${months} months of expenses as buffer`
                : `Threshold: ${JSON.stringify(rule.threshold_config)}`}
            </div>
          </NeuroCard>
        );
      })}
    </div>
  );
}

export function RightSidebar({ activeTab, setActiveTab, rules, metrics, collapsed, onToggleCollapse }: RightSidebarProps) {
  const { user } = useAuth();
  const [decisionItems, setDecisionItems] = useState<DecisionItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch alerts from API
  useEffect(() => {
    if (!user) return;

    const fetchAlerts = async () => {
      setIsLoading(true);
      try {
        const [risksResponse, controlsResponse] = await Promise.all([
          getRisks({ status: 'active' }),
          getControls(),
        ]);

        // Build risk-control map
        const riskControlMap = new Map<string, string[]>();
        risksResponse.risks.forEach((risk: Risk) => {
          riskControlMap.set(risk.id, risk.linked_control_ids || []);
        });
        controlsResponse.controls.forEach((control: Control) => {
          control.linked_risk_ids.forEach((riskId: string) => {
            const existing = riskControlMap.get(riskId) || [];
            if (!existing.includes(control.id)) {
              riskControlMap.set(riskId, [...existing, control.id]);
            }
          });
        });

        // Build decision queue
        const { items } = buildDecisionQueue(
          risksResponse.risks,
          controlsResponse.controls,
          riskControlMap
        );

        setDecisionItems(items);
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAlerts();
  }, [user]);

  // Calculate alert counts
  const alertCount = useMemo(() =>
    decisionItems.filter((item) => item.section === 'requires_decision').length,
    [decisionItems]
  );
  const totalAlerts = decisionItems.length;
  const needsAttention = totalAlerts > 0 || metrics.runwayWeeks < 8;

  // Collapsed state - show minimal bar with toggle and alert indicator
  if (collapsed) {
    return (
      <aside className="w-12 glass rounded-xl flex flex-col items-center py-3 gap-3 transition-all duration-300">
        {/* Expand button */}
        <button
          onClick={onToggleCollapse}
          className="w-8 h-8 rounded-lg bg-white/50 hover:bg-white text-muted-foreground hover:text-gunmetal flex items-center justify-center transition-all"
          title="Expand sidebar"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Alert indicator */}
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center relative cursor-pointer',
            needsAttention ? 'bg-amber-500 text-white' : 'bg-lime-dark text-white'
          )}
          onClick={onToggleCollapse}
          title={needsAttention ? `${alertCount} items need attention` : 'All systems healthy'}
        >
          <AlertCircle className="w-4 h-4" />
          {alertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-tomato rounded-full text-[10px] font-semibold flex items-center justify-center text-white">
              {alertCount}
            </span>
          )}
        </div>
      </aside>
    );
  }

  // Expanded state - full sidebar
  return (
    <aside className="w-[320px] glass rounded-xl flex flex-col overflow-hidden transition-all duration-300">
      {/* Header with tabs and collapse button aligned */}
      <div className="px-3 py-2 border-b border-border/50 flex items-center gap-2">
        <div className="flex-1">
          <SidebarTabs activeTab={activeTab} setActiveTab={setActiveTab} rules={rules} totalAlerts={totalAlerts} />
        </div>
        <button
          onClick={onToggleCollapse}
          className="w-7 h-7 rounded-lg bg-white/50 hover:bg-white text-muted-foreground hover:text-gunmetal flex items-center justify-center transition-all flex-shrink-0"
          title="Collapse sidebar"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'alerts' && <AlertsPanel decisionItems={decisionItems} isLoading={isLoading} />}
        {activeTab === 'activity' && <ActivityPanel />}
        {activeTab === 'rules' && <RulesPanel rules={rules} />}
      </div>
    </aside>
  );
}
