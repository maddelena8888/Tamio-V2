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
import { type RuleConfig, type PayrollConfig } from '@/lib/api/rules';

interface PayrollFieldsProps {
  config: RuleConfig;
  onChange: (config: RuleConfig) => void;
}

export function PayrollFields({ config, onChange }: PayrollFieldsProps) {
  const c = config as PayrollConfig;

  const handleChange = <K extends keyof PayrollConfig>(
    field: K,
    value: PayrollConfig[K]
  ) => {
    onChange({
      ...c,
      [field]: value,
    });
  };

  return (
    <div className="space-y-6">
      {/* Payroll Amount */}
      <div className="space-y-2">
        <Label>Monthly payroll amount</Label>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Checkbox
              id="auto_detect"
              checked={c.auto_detect_enabled}
              onCheckedChange={(checked) => handleChange('auto_detect_enabled', checked as boolean)}
            />
            <Label htmlFor="auto_detect" className="cursor-pointer">
              Auto-detect from payment history
            </Label>
          </div>

          {!c.auto_detect_enabled && (
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                £
              </span>
              <Input
                type="number"
                value={c.payroll_amount}
                onChange={(e) => handleChange('payroll_amount', Number(e.target.value))}
                className="pl-7"
                placeholder="23500"
              />
            </div>
          )}

          {c.auto_detect_enabled && (
            <p className="text-sm text-muted-foreground p-3 rounded-lg bg-white/30">
              Based on your payment history, average monthly payroll is approximately{' '}
              <span className="font-medium text-gunmetal">£23,500</span>
            </p>
          )}
        </div>
      </div>

      {/* Pay Date */}
      <div className="space-y-2">
        <Label>Pay date</Label>
        <Select
          value={c.pay_date_type}
          onValueChange={(value) => handleChange('pay_date_type', value as PayrollConfig['pay_date_type'])}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="day_of_month">Day of month</SelectItem>
            <SelectItem value="specific_dates">Specific dates</SelectItem>
          </SelectContent>
        </Select>

        {c.pay_date_type === 'day_of_month' && (
          <div className="flex items-center gap-2 mt-2">
            <span className="text-muted-foreground">Pay on the</span>
            <Select
              value={String(c.pay_day)}
              onValueChange={(value) => handleChange('pay_day', Number(value))}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
                  <SelectItem key={day} value={String(day)}>
                    {day}{day === 1 ? 'st' : day === 2 ? 'nd' : day === 3 ? 'rd' : 'th'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-muted-foreground">of each month</span>
          </div>
        )}
      </div>

      {/* Alert Timing */}
      <div className="space-y-2">
        <Label>Alert timing</Label>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Alert me</span>
          <Input
            type="number"
            value={c.alert_days_before}
            onChange={(e) => handleChange('alert_days_before', Number(e.target.value))}
            className="w-20"
            min={1}
            max={30}
          />
          <span className="text-muted-foreground">days before payday if coverage is at risk</span>
        </div>
      </div>

      {/* Buffer Amount */}
      <div className="space-y-2">
        <Label>Include buffer (optional)</Label>
        <p className="text-sm text-muted-foreground">
          Ensure extra funds beyond the payroll amount
        </p>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
            £
          </span>
          <Input
            type="number"
            value={c.buffer_amount}
            onChange={(e) => handleChange('buffer_amount', Number(e.target.value))}
            className="pl-7"
            placeholder="0"
          />
        </div>
      </div>
    </div>
  );
}
