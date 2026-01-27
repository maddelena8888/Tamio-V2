import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import type { ContractorParams } from '../mockData';

interface ContractorFieldsProps {
  isGain: boolean;
  params: Partial<ContractorParams>;
  onChange: (params: Partial<ContractorParams>) => void;
}

export function ContractorFields({ isGain, params, onChange }: ContractorFieldsProps) {
  const dateLabel = isGain ? 'Start Date' : 'End Date';

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Contractor Name (optional) */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Contractor Name <span className="text-gunmetal/50">(optional)</span>
          </Label>
          <Input
            type="text"
            placeholder="e.g., Jane Smith"
            value={params.contractorName || ''}
            onChange={(e) => onChange({ ...params, contractorName: e.target.value || undefined })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Start/End Date */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            {dateLabel}
          </Label>
          <Input
            type="date"
            value={params.date || ''}
            onChange={(e) => onChange({ ...params, date: e.target.value })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Monthly Estimate */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Monthly Estimate ($)
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 5000"
            value={params.monthlyEstimate ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, monthlyEstimate: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>
      </div>

      {/* Recurring Toggle */}
      <div className="flex items-center space-x-2">
        <Checkbox
          id="is-recurring"
          checked={params.isRecurring ?? true}
          onCheckedChange={(checked) => onChange({ ...params, isRecurring: checked === true })}
        />
        <Label htmlFor="is-recurring" className="text-sm text-gunmetal cursor-pointer">
          Recurring monthly expense
        </Label>
      </div>
    </div>
  );
}
