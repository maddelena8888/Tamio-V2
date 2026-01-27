import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import type { ExpenseParams } from '../mockData';

interface ExpenseFieldsProps {
  isIncrease: boolean;
  params: Partial<ExpenseParams>;
  onChange: (params: Partial<ExpenseParams>) => void;
}

const FREQUENCIES = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'annual', label: 'Annual' },
] as const;

export function ExpenseFields({ isIncrease, params, onChange }: ExpenseFieldsProps) {
  const amountLabel = isIncrease ? 'Increase Amount ($)' : 'Decrease Amount ($)';

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Expense Name */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Expense Name
          </Label>
          <Input
            type="text"
            placeholder="e.g., AWS Infrastructure"
            value={params.expenseName || ''}
            onChange={(e) => onChange({ ...params, expenseName: e.target.value })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Amount */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            {amountLabel}
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 500"
            value={params.amount ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, amount: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Effective Date */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Effective Date
          </Label>
          <Input
            type="date"
            value={params.effectiveDate || ''}
            onChange={(e) => onChange({ ...params, effectiveDate: e.target.value })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-6">
        {/* Recurring Toggle */}
        <div className="flex items-center space-x-2">
          <Checkbox
            id="expense-recurring"
            checked={params.isRecurring ?? false}
            onCheckedChange={(checked) => {
              const isRecurring = checked === true;
              onChange({
                ...params,
                isRecurring,
                frequency: isRecurring ? (params.frequency || 'monthly') : undefined
              });
            }}
          />
          <Label htmlFor="expense-recurring" className="text-sm text-gunmetal cursor-pointer">
            Recurring expense
          </Label>
        </div>

        {/* Frequency (only shown if recurring) */}
        {params.isRecurring && (
          <div className="flex items-center gap-2">
            <Label className="text-sm text-gunmetal">Frequency:</Label>
            <Select
              value={params.frequency || 'monthly'}
              onValueChange={(v) => onChange({ ...params, frequency: v as ExpenseParams['frequency'] })}
            >
              <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FREQUENCIES.map((freq) => (
                  <SelectItem key={freq.value} value={freq.value}>
                    {freq.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
    </div>
  );
}
