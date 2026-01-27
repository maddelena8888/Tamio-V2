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
import type { ClientLossParams } from '../mockData';
import { MOCK_CLIENTS } from '../mockData';

interface ClientLossFieldsProps {
  params: Partial<ClientLossParams>;
  onChange: (params: Partial<ClientLossParams>) => void;
}

export function ClientLossFields({ params, onChange }: ClientLossFieldsProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Client Selector */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Client
          </Label>
          <Select
            value={params.clientId || ''}
            onValueChange={(v) => onChange({ ...params, clientId: v })}
          >
            <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full">
              <SelectValue placeholder="Select client" />
            </SelectTrigger>
            <SelectContent>
              {MOCK_CLIENTS.map((client) => (
                <SelectItem key={client.id} value={client.id}>
                  {client.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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

        {/* Variable Cost Reduction (optional) */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Variable Cost Reduction % <span className="text-gunmetal/50">(optional)</span>
          </Label>
          <Input
            type="number"
            min={0}
            max={100}
            placeholder="e.g., 20"
            value={params.reduceVariableCosts ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseInt(e.target.value);
              onChange({ ...params, reduceVariableCosts: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>
      </div>

      {/* Impact Options */}
      <div className="flex flex-wrap gap-6">
        <div className="flex items-center space-x-2">
          <Checkbox
            id="impact-retainers"
            checked={params.impactRetainers ?? true}
            onCheckedChange={(checked) => onChange({ ...params, impactRetainers: checked === true })}
          />
          <Label htmlFor="impact-retainers" className="text-sm text-gunmetal cursor-pointer">
            Impact retainer revenue
          </Label>
        </div>

        <div className="flex items-center space-x-2">
          <Checkbox
            id="impact-milestones"
            checked={params.impactMilestones ?? true}
            onCheckedChange={(checked) => onChange({ ...params, impactMilestones: checked === true })}
          />
          <Label htmlFor="impact-milestones" className="text-sm text-gunmetal cursor-pointer">
            Impact milestone payments
          </Label>
        </div>
      </div>
    </div>
  );
}
