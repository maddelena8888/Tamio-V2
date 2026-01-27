import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { PaymentDelayParams } from '../mockData';
import { MOCK_CLIENTS, MOCK_VENDORS } from '../mockData';

interface PaymentDelayFieldsProps {
  isIncoming: boolean;
  params: Partial<PaymentDelayParams>;
  onChange: (params: Partial<PaymentDelayParams>) => void;
}

export function PaymentDelayFields({ isIncoming, params, onChange }: PaymentDelayFieldsProps) {
  const entities = isIncoming ? MOCK_CLIENTS : MOCK_VENDORS;
  const entityLabel = isIncoming ? 'Client' : 'Vendor';

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Client/Vendor Selector */}
      <div className="space-y-2">
        <Label className="text-sm font-medium text-gunmetal">
          {entityLabel}
        </Label>
        <Select
          value={params.clientOrVendor || ''}
          onValueChange={(v) => onChange({ ...params, clientOrVendor: v })}
        >
          <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full">
            <SelectValue placeholder={`Select ${entityLabel.toLowerCase()}`} />
          </SelectTrigger>
          <SelectContent>
            {entities.map((entity) => (
              <SelectItem key={entity.id} value={entity.id}>
                {entity.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Delay Weeks */}
      <div className="space-y-2">
        <Label className="text-sm font-medium text-gunmetal">
          Delay (Weeks)
        </Label>
        <Input
          type="number"
          min={1}
          max={52}
          placeholder="e.g., 4"
          value={params.delayWeeks || ''}
          onChange={(e) => onChange({ ...params, delayWeeks: parseInt(e.target.value) || undefined })}
          className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
        />
      </div>

      {/* Partial Payment Percentage (optional) */}
      <div className="space-y-2">
        <Label className="text-sm font-medium text-gunmetal">
          Partial Payment % <span className="text-gunmetal/50">(optional)</span>
        </Label>
        <Input
          type="number"
          min={0}
          max={100}
          placeholder="e.g., 50"
          value={params.partialPaymentPct ?? ''}
          onChange={(e) => {
            const val = e.target.value === '' ? undefined : parseInt(e.target.value);
            onChange({ ...params, partialPaymentPct: val });
          }}
          className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
        />
      </div>
    </div>
  );
}
