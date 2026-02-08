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
import { type RuleConfig, type TaxVATConfig } from '@/lib/api/rules';

interface TaxVATFieldsProps {
  config: RuleConfig;
  onChange: (config: RuleConfig) => void;
}

export function TaxVATFields({ config, onChange }: TaxVATFieldsProps) {
  const c = config as TaxVATConfig;

  const handleChange = <K extends keyof TaxVATConfig>(
    field: K,
    value: TaxVATConfig[K]
  ) => {
    onChange({
      ...c,
      [field]: value,
    });
  };

  return (
    <div className="space-y-6">
      {/* Tax Type */}
      <div className="space-y-2">
        <Label>Tax type</Label>
        <Select
          value={c.tax_type}
          onValueChange={(value) => handleChange('tax_type', value as TaxVATConfig['tax_type'])}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="vat">VAT</SelectItem>
            <SelectItem value="corporation_tax">Corporation Tax</SelectItem>
            <SelectItem value="custom">Custom</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Custom Name (if custom) */}
      {c.tax_type === 'custom' && (
        <div className="space-y-2">
          <Label>Custom tax name</Label>
          <Input
            value={c.custom_name || ''}
            onChange={(e) => handleChange('custom_name', e.target.value)}
            placeholder="e.g., Income Tax"
          />
        </div>
      )}

      {/* Calculation Method */}
      <div className="space-y-2">
        <Label>Calculation method</Label>
        <p className="text-sm text-muted-foreground">
          {c.tax_type === 'vat'
            ? 'Set aside a percentage of incoming payments'
            : 'Set aside a percentage of revenue'}
        </p>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Set aside</span>
          <Input
            type="number"
            value={c.percentage}
            onChange={(e) => handleChange('percentage', Number(e.target.value))}
            className="w-20"
            min={0}
            max={100}
          />
          <span className="text-muted-foreground">% of</span>
          <Select
            value={c.calculation_source}
            onValueChange={(value) => handleChange('calculation_source', value as TaxVATConfig['calculation_source'])}
          >
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="incoming_payments">incoming payments</SelectItem>
              <SelectItem value="revenue">revenue</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Alert Threshold */}
      <div className="space-y-2">
        <Label>Alert threshold</Label>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Alert when reserve shortfall exceeds</span>
          <div className="relative w-32">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              £
            </span>
            <Input
              type="number"
              value={c.alert_threshold_value}
              onChange={(e) => handleChange('alert_threshold_value', Number(e.target.value))}
              className="pl-7"
            />
          </div>
        </div>
      </div>

      {/* Due Date Reminder */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Checkbox
            id="due_date_reminder"
            checked={c.due_date_reminder_enabled}
            onCheckedChange={(checked) => handleChange('due_date_reminder_enabled', checked as boolean)}
          />
          <Label htmlFor="due_date_reminder" className="cursor-pointer">
            Also remind me before tax is due
          </Label>
        </div>

        {c.due_date_reminder_enabled && (
          <div className="flex items-center gap-2 ml-6">
            <span className="text-muted-foreground">Remind me</span>
            <Input
              type="number"
              value={c.due_date_reminder_days || 14}
              onChange={(e) => handleChange('due_date_reminder_days', Number(e.target.value))}
              className="w-20"
              min={1}
              max={90}
            />
            <span className="text-muted-foreground">days before deadline</span>
          </div>
        )}
      </div>

      {/* Current Liability Display */}
      <div className="p-3 rounded-lg bg-white/30 border border-white/40">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
          Current {c.tax_type === 'custom' ? c.custom_name || 'Tax' : c.tax_type.toUpperCase()} Liability Estimate
        </p>
        <p className="text-lg font-semibold text-gunmetal">£12,340</p>
        <p className="text-xs text-muted-foreground">Based on recent transactions</p>
      </div>
    </div>
  );
}
