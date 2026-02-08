import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { type RuleConfig, type CashBufferConfig, type AlertSeverity } from '@/lib/api/rules';

interface CashBufferFieldsProps {
  config: RuleConfig;
  onChange: (config: RuleConfig) => void;
}

export function CashBufferFields({ config, onChange }: CashBufferFieldsProps) {
  const c = config as CashBufferConfig;

  const handleChange = <K extends keyof CashBufferConfig>(
    field: K,
    value: CashBufferConfig[K]
  ) => {
    onChange({
      ...c,
      [field]: value,
    });
  };

  return (
    <div className="space-y-6">
      {/* Threshold Type */}
      <div className="space-y-3">
        <Label>Alert when cash falls below:</Label>
        <RadioGroup
          value={c.threshold_type}
          onValueChange={(value) => handleChange('threshold_type', value as 'fixed_amount' | 'days_of_expenses')}
          className="space-y-3"
        >
          <div className="flex items-start gap-3">
            <RadioGroupItem value="fixed_amount" id="fixed_amount" className="mt-1" />
            <div className="flex-1">
              <Label htmlFor="fixed_amount" className="cursor-pointer font-medium">
                Fixed amount
              </Label>
              {c.threshold_type === 'fixed_amount' && (
                <div className="mt-2">
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                      £
                    </span>
                    <Input
                      type="number"
                      value={c.threshold_amount}
                      onChange={(e) => handleChange('threshold_amount', Number(e.target.value))}
                      className="pl-7"
                      placeholder="50000"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-start gap-3">
            <RadioGroupItem value="days_of_expenses" id="days_of_expenses" className="mt-1" />
            <div className="flex-1">
              <Label htmlFor="days_of_expenses" className="cursor-pointer font-medium">
                Days of operating expenses
              </Label>
              {c.threshold_type === 'days_of_expenses' && (
                <div className="mt-2 space-y-2">
                  <Input
                    type="number"
                    value={c.days_of_expenses || 30}
                    onChange={(e) => handleChange('days_of_expenses', Number(e.target.value))}
                    placeholder="30"
                    min={1}
                    max={365}
                  />
                  <p className="text-xs text-muted-foreground">
                    Based on your average daily expenses, this equals approximately £
                    {((c.days_of_expenses || 30) * 1667).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          </div>
        </RadioGroup>
      </div>

      {/* Look-ahead Period */}
      <div className="space-y-2">
        <Label>Look-ahead period</Label>
        <p className="text-sm text-muted-foreground">
          How far into the forecast should we monitor?
        </p>
        <Select
          value={c.look_ahead_period}
          onValueChange={(value) => handleChange('look_ahead_period', value as CashBufferConfig['look_ahead_period'])}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="2_weeks">2 weeks</SelectItem>
            <SelectItem value="1_month">1 month</SelectItem>
            <SelectItem value="3_months">3 months</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Alert Severity */}
      <div className="space-y-2">
        <Label>Alert severity</Label>
        <Select
          value={c.severity}
          onValueChange={(value) => handleChange('severity', value as AlertSeverity)}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="warning">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Warning (Amber)
              </span>
            </SelectItem>
            <SelectItem value="urgent">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-tomato" />
                Urgent (Red)
              </span>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
