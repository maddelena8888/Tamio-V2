import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { HiringParams } from '../mockData';

interface HiringFieldsProps {
  params: Partial<HiringParams>;
  onChange: (params: Partial<HiringParams>) => void;
}

const PAY_FREQUENCIES = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'bi-weekly', label: 'Bi-weekly' },
  { value: 'weekly', label: 'Weekly' },
] as const;

export function HiringFields({ params, onChange }: HiringFieldsProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Role Title */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Role Title
          </Label>
          <Input
            type="text"
            placeholder="e.g., Senior Developer"
            value={params.roleTitle || ''}
            onChange={(e) => onChange({ ...params, roleTitle: e.target.value })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Start Date */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Start Date
          </Label>
          <Input
            type="date"
            value={params.startDate || ''}
            onChange={(e) => onChange({ ...params, startDate: e.target.value })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Pay Frequency */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Pay Frequency
          </Label>
          <Select
            value={params.payFrequency || 'monthly'}
            onValueChange={(v) => onChange({ ...params, payFrequency: v as HiringParams['payFrequency'] })}
          >
            <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full">
              <SelectValue placeholder="Select frequency" />
            </SelectTrigger>
            <SelectContent>
              {PAY_FREQUENCIES.map((freq) => (
                <SelectItem key={freq.value} value={freq.value}>
                  {freq.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Monthly Cost */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Monthly Cost ($)
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 8000"
            value={params.monthlyCost ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, monthlyCost: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Onboarding Costs (optional) */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Onboarding Costs ($) <span className="text-gunmetal/50">(optional)</span>
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 2000"
            value={params.onboardingCosts ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, onboardingCosts: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>
      </div>
    </div>
  );
}
