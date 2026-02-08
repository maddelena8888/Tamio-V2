import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { type RuleConfig, type ReceivablesConfig } from '@/lib/api/rules';

interface ReceivablesFieldsProps {
  config: RuleConfig;
  onChange: (config: RuleConfig) => void;
}

type EscalationSeverity = 'nudge' | 'warning' | 'urgent';

export function ReceivablesFields({ config, onChange }: ReceivablesFieldsProps) {
  const c = config as ReceivablesConfig;

  const handleChange = <K extends keyof ReceivablesConfig>(
    field: K,
    value: ReceivablesConfig[K]
  ) => {
    onChange({
      ...c,
      [field]: value,
    });
  };

  const handleEscalationChange = (
    tier: 'tier1' | 'tier2' | 'tier3',
    field: 'days' | 'severity',
    value: number | EscalationSeverity
  ) => {
    const currentTiers = c.escalation_tiers || {
      tier1_days: 7,
      tier1_severity: 'nudge' as EscalationSeverity,
      tier2_days: 14,
      tier2_severity: 'warning' as EscalationSeverity,
      tier3_days: 30,
      tier3_severity: 'urgent' as EscalationSeverity,
    };

    handleChange('escalation_tiers', {
      ...currentTiers,
      [`${tier}_${field}`]: value,
    });
  };

  return (
    <div className="space-y-6">
      {/* Basic Overdue Days */}
      <div className="space-y-2">
        <Label>Alert when invoice is overdue by</Label>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            value={c.overdue_days}
            onChange={(e) => handleChange('overdue_days', Number(e.target.value))}
            className="w-24"
            min={1}
            max={365}
          />
          <span className="text-muted-foreground">days</span>
        </div>
      </div>

      {/* Minimum Invoice Amount */}
      <div className="space-y-2">
        <Label>Minimum invoice amount</Label>
        <p className="text-sm text-muted-foreground">
          Only alert for invoices above this amount (to ignore small invoices)
        </p>
        <div className="relative w-40">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
            £
          </span>
          <Input
            type="number"
            value={c.minimum_invoice_amount}
            onChange={(e) => handleChange('minimum_invoice_amount', Number(e.target.value))}
            className="pl-7"
          />
        </div>
      </div>

      {/* Escalation Tiers */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Checkbox
            id="escalation_enabled"
            checked={c.escalation_enabled}
            onCheckedChange={(checked) => {
              handleChange('escalation_enabled', checked as boolean);
              if (checked && !c.escalation_tiers) {
                handleChange('escalation_tiers', {
                  tier1_days: 7,
                  tier1_severity: 'nudge',
                  tier2_days: 14,
                  tier2_severity: 'warning',
                  tier3_days: 30,
                  tier3_severity: 'urgent',
                });
              }
            }}
          />
          <Label htmlFor="escalation_enabled" className="cursor-pointer">
            Enable escalation tiers
          </Label>
        </div>

        {c.escalation_enabled && c.escalation_tiers && (
          <div className="space-y-3 ml-6 p-4 rounded-lg bg-white/30">
            {(['tier1', 'tier2', 'tier3'] as const).map((tier, index) => (
              <div key={tier} className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground w-16">Tier {index + 1}:</span>
                <Input
                  type="number"
                  value={c.escalation_tiers?.[`${tier}_days`]}
                  onChange={(e) => handleEscalationChange(tier, 'days', Number(e.target.value))}
                  className="w-20"
                  min={1}
                />
                <span className="text-sm text-muted-foreground">days →</span>
                <Select
                  value={c.escalation_tiers?.[`${tier}_severity`]}
                  onValueChange={(value) => handleEscalationChange(tier, 'severity', value as EscalationSeverity)}
                >
                  <SelectTrigger className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="nudge">Nudge</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Customer Filter */}
      <div className="space-y-2">
        <Label>Customer filter</Label>
        <Select
          value={c.customer_filter}
          onValueChange={(value) => handleChange('customer_filter', value as ReceivablesConfig['customer_filter'])}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All customers</SelectItem>
            <SelectItem value="specific">Specific customers only</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Aggregate Alert */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Checkbox
            id="aggregate_alert"
            checked={c.aggregate_alert_enabled}
            onCheckedChange={(checked) => handleChange('aggregate_alert_enabled', checked as boolean)}
          />
          <Label htmlFor="aggregate_alert" className="cursor-pointer">
            Also alert when total overdue receivables exceed a threshold
          </Label>
        </div>

        {c.aggregate_alert_enabled && (
          <div className="flex items-center gap-2 ml-6">
            <span className="text-muted-foreground">Alert when total exceeds</span>
            <div className="relative w-32">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                £
              </span>
              <Input
                type="number"
                value={c.aggregate_threshold || 10000}
                onChange={(e) => handleChange('aggregate_threshold', Number(e.target.value))}
                className="pl-7"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
