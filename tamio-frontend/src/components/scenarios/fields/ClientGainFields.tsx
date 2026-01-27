import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ClientGainParams } from '../mockData';

interface ClientGainFieldsProps {
  params: Partial<ClientGainParams>;
  onChange: (params: Partial<ClientGainParams>) => void;
}

const AGREEMENT_TYPES = [
  { value: 'retainer', label: 'Retainer' },
  { value: 'project', label: 'Project-based' },
  { value: 'usage', label: 'Usage-based' },
  { value: 'mixed', label: 'Mixed' },
] as const;

const BILLING_FREQUENCIES = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'annual', label: 'Annual' },
] as const;

export function ClientGainFields({ params, onChange }: ClientGainFieldsProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Client Name */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Client Name
          </Label>
          <Input
            type="text"
            placeholder="e.g., NewCorp Inc."
            value={params.clientName || ''}
            onChange={(e) => onChange({ ...params, clientName: e.target.value })}
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

        {/* Agreement Type */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Agreement Type
          </Label>
          <Select
            value={params.agreementType || ''}
            onValueChange={(v) => onChange({ ...params, agreementType: v as ClientGainParams['agreementType'] })}
          >
            <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full">
              <SelectValue placeholder="Select type" />
            </SelectTrigger>
            <SelectContent>
              {AGREEMENT_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Monthly Amount */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Monthly Amount ($)
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 5000"
            value={params.monthlyAmount ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, monthlyAmount: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

        {/* Billing Frequency */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Billing Frequency
          </Label>
          <Select
            value={params.billingFrequency || ''}
            onValueChange={(v) => onChange({ ...params, billingFrequency: v as ClientGainParams['billingFrequency'] })}
          >
            <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full">
              <SelectValue placeholder="Select frequency" />
            </SelectTrigger>
            <SelectContent>
              {BILLING_FREQUENCIES.map((freq) => (
                <SelectItem key={freq.value} value={freq.value}>
                  {freq.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Additional Variable Costs (optional) */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Add Variable Costs ($) <span className="text-gunmetal/50">(optional)</span>
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 500"
            value={params.addVariableCosts ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, addVariableCosts: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>
      </div>
    </div>
  );
}
