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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { type RuleConfig, type UnusualActivityConfig } from '@/lib/api/rules';

interface UnusualActivityFieldsProps {
  config: RuleConfig;
  onChange: (config: RuleConfig) => void;
}

export function UnusualActivityFields({ config, onChange }: UnusualActivityFieldsProps) {
  const c = config as UnusualActivityConfig;

  const handleChange = <K extends keyof UnusualActivityConfig>(
    field: K,
    value: UnusualActivityConfig[K]
  ) => {
    onChange({
      ...c,
      [field]: value,
    });
  };

  const sensitivityPercent = {
    conservative: 50,
    moderate: 25,
    sensitive: 10,
    custom: c.custom_threshold_percent || 25,
  };

  return (
    <div className="space-y-6">
      {/* Monitor Type */}
      <div className="space-y-2">
        <Label>What to monitor</Label>
        <Select
          value={c.monitor_type}
          onValueChange={(value) => handleChange('monitor_type', value as UnusualActivityConfig['monitor_type'])}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all_spending">All spending</SelectItem>
            <SelectItem value="specific_category">Specific category</SelectItem>
            <SelectItem value="specific_vendor">Specific vendor</SelectItem>
          </SelectContent>
        </Select>

        {(c.monitor_type === 'specific_category' || c.monitor_type === 'specific_vendor') && (
          <Input
            value={c.specific_value || ''}
            onChange={(e) => handleChange('specific_value', e.target.value)}
            placeholder={c.monitor_type === 'specific_category' ? 'e.g., Marketing' : 'e.g., AWS'}
            className="mt-2"
          />
        )}
      </div>

      {/* Sensitivity Threshold */}
      <div className="space-y-3">
        <Label>Sensitivity threshold</Label>
        <p className="text-sm text-muted-foreground">
          Alert when spending exceeds normal by this percentage
        </p>

        <RadioGroup
          value={c.sensitivity_preset}
          onValueChange={(value) => handleChange('sensitivity_preset', value as UnusualActivityConfig['sensitivity_preset'])}
          className="space-y-2"
        >
          <div className="flex items-center gap-3">
            <RadioGroupItem value="conservative" id="conservative" />
            <Label htmlFor="conservative" className="cursor-pointer">
              Conservative (50% above normal)
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <RadioGroupItem value="moderate" id="moderate" />
            <Label htmlFor="moderate" className="cursor-pointer">
              Moderate (25% above normal)
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <RadioGroupItem value="sensitive" id="sensitive" />
            <Label htmlFor="sensitive" className="cursor-pointer">
              Sensitive (10% above normal)
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <RadioGroupItem value="custom" id="custom" />
            <Label htmlFor="custom" className="cursor-pointer">
              Custom
            </Label>
            {c.sensitivity_preset === 'custom' && (
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  value={c.custom_threshold_percent || 25}
                  onChange={(e) => handleChange('custom_threshold_percent', Number(e.target.value))}
                  className="w-20"
                  min={1}
                  max={200}
                />
                <span className="text-muted-foreground">%</span>
              </div>
            )}
          </div>
        </RadioGroup>
      </div>

      {/* Comparison Period */}
      <div className="space-y-2">
        <Label>Comparison period</Label>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Compare against average of last</span>
          <Select
            value={String(c.comparison_months)}
            onValueChange={(value) => handleChange('comparison_months', Number(value))}
          >
            <SelectTrigger className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 month</SelectItem>
              <SelectItem value="3">3 months</SelectItem>
              <SelectItem value="6">6 months</SelectItem>
              <SelectItem value="12">12 months</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Minimum Amount */}
      <div className="space-y-2">
        <Label>Minimum overspend amount</Label>
        <p className="text-sm text-muted-foreground">
          Only alert if the overspend exceeds this amount (to avoid noise)
        </p>
        <div className="relative w-40">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
            £
          </span>
          <Input
            type="number"
            value={c.minimum_overspend_amount}
            onChange={(e) => handleChange('minimum_overspend_amount', Number(e.target.value))}
            className="pl-7"
          />
        </div>
      </div>

      {/* Alert Direction */}
      <div className="space-y-3">
        <Label>Alert direction</Label>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Checkbox
              id="alert_overspending"
              checked={c.alert_on_overspending}
              onCheckedChange={(checked) => handleChange('alert_on_overspending', checked as boolean)}
            />
            <Label htmlFor="alert_overspending" className="cursor-pointer">
              Alert on overspending
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <Checkbox
              id="alert_unusual_income"
              checked={c.alert_on_unusual_income}
              onCheckedChange={(checked) => handleChange('alert_on_unusual_income', checked as boolean)}
            />
            <Label htmlFor="alert_unusual_income" className="cursor-pointer">
              Alert on unusual income (optional)
            </Label>
          </div>
        </div>
      </div>

      {/* Preview of current threshold */}
      <div className="p-3 rounded-lg bg-white/30 border border-white/40">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
          Current Threshold
        </p>
        <p className="text-sm text-gunmetal">
          Alert when {c.monitor_type === 'all_spending' ? 'any category' : c.specific_value || 'selected item'} exceeds
          the {c.comparison_months}-month average by more than {sensitivityPercent[c.sensitivity_preset]}%
          {c.minimum_overspend_amount > 0 && `, if the difference is at least £${c.minimum_overspend_amount.toLocaleString()}`}
        </p>
      </div>
    </div>
  );
}
