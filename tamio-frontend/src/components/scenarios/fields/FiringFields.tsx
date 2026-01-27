import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { FiringParams } from '../mockData';
import { MOCK_EMPLOYEES } from '../mockData';

interface FiringFieldsProps {
  params: Partial<FiringParams>;
  onChange: (params: Partial<FiringParams>) => void;
}

export function FiringFields({ params, onChange }: FiringFieldsProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Employee Selector (optional) */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Employee <span className="text-gunmetal/50">(optional)</span>
          </Label>
          <Select
            value={params.employeeId || '__none__'}
            onValueChange={(v) => onChange({ ...params, employeeId: v === '__none__' ? undefined : v })}
          >
            <SelectTrigger className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full">
              <SelectValue placeholder="Select employee (optional)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">No specific employee</SelectItem>
              {MOCK_EMPLOYEES.map((emp) => (
                <SelectItem key={emp.id} value={emp.id}>
                  {emp.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* End Date */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            End Date
          </Label>
          <Input
            type="date"
            value={params.endDate || ''}
            onChange={(e) => onChange({ ...params, endDate: e.target.value })}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>

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
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Severance Amount (optional) */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-gunmetal">
            Severance Amount ($) <span className="text-gunmetal/50">(optional)</span>
          </Label>
          <Input
            type="number"
            min={0}
            placeholder="e.g., 15000"
            value={params.severanceAmount ?? ''}
            onChange={(e) => {
              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
              onChange({ ...params, severanceAmount: val });
            }}
            className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
          />
        </div>
      </div>
    </div>
  );
}
