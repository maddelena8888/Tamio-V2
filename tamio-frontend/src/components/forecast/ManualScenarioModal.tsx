import { useState, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2 } from 'lucide-react';
import type { ScenarioType } from '@/lib/api/types';

const SCENARIO_TYPE_OPTIONS: { value: ScenarioType; label: string }[] = [
  { value: 'payment_delay_in', label: 'Payment Delay (Incoming)' },
  { value: 'payment_delay_out', label: 'Payment Delay (Outgoing)' },
  { value: 'client_loss', label: 'Client Loss' },
  { value: 'client_gain', label: 'Client Gain' },
  { value: 'hiring', label: 'New Hire' },
  { value: 'firing', label: 'Layoff / Termination' },
  { value: 'contractor_gain', label: 'Add Contractor' },
  { value: 'contractor_loss', label: 'Remove Contractor' },
  { value: 'increased_expense', label: 'Expense Increase' },
  { value: 'decreased_expense', label: 'Expense Decrease' },
];

export interface ManualScenarioParams {
  name: string;
  type: ScenarioType;
  effectiveDate: string;
  params: Record<string, unknown>;
}

interface ManualScenarioModalProps {
  isOpen: boolean;
  onClose: () => void;
  onBuild: (params: ManualScenarioParams) => Promise<void>;
}

export function ManualScenarioModal({
  isOpen,
  onClose,
  onBuild,
}: ManualScenarioModalProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState<ScenarioType | ''>('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [isBuilding, setIsBuilding] = useState(false);

  // Type-specific params
  const [delayDays, setDelayDays] = useState('30');
  const [amount, setAmount] = useState('');
  const [percentage, setPercentage] = useState('25');

  const resetForm = useCallback(() => {
    setName('');
    setType('');
    setEffectiveDate('');
    setDelayDays('30');
    setAmount('');
    setPercentage('25');
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  const handleBuild = useCallback(async () => {
    if (!name || !type || !effectiveDate) return;

    setIsBuilding(true);
    try {
      // Build params based on scenario type
      let params: Record<string, unknown> = {};

      switch (type) {
        case 'payment_delay_in':
        case 'payment_delay_out':
          params = { delay_days: parseInt(delayDays, 10) };
          break;
        case 'hiring':
        case 'firing':
        case 'contractor_gain':
        case 'contractor_loss':
          params = { monthly_amount: parseFloat(amount) || 0 };
          break;
        case 'increased_expense':
        case 'decreased_expense':
          params = { percentage: parseInt(percentage, 10) };
          break;
        case 'client_loss':
        case 'client_gain':
          params = { monthly_amount: parseFloat(amount) || 0 };
          break;
      }

      await onBuild({
        name,
        type: type as ScenarioType,
        effectiveDate,
        params,
      });

      handleClose();
    } finally {
      setIsBuilding(false);
    }
  }, [name, type, effectiveDate, delayDays, amount, percentage, onBuild, handleClose]);

  const isValid = name.trim() && type && effectiveDate;

  // Render type-specific fields
  const renderTypeFields = () => {
    if (!type) return null;

    switch (type) {
      case 'payment_delay_in':
      case 'payment_delay_out':
        return (
          <div className="space-y-2">
            <Label htmlFor="delay-days" className="text-sm font-medium text-gunmetal">
              Delay (days)
            </Label>
            <Select value={delayDays} onValueChange={setDelayDays}>
              <SelectTrigger className="bg-white/50 border-gunmetal/20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="14">14 days</SelectItem>
                <SelectItem value="30">30 days</SelectItem>
                <SelectItem value="60">60 days</SelectItem>
                <SelectItem value="90">90 days</SelectItem>
              </SelectContent>
            </Select>
          </div>
        );

      case 'hiring':
      case 'firing':
      case 'contractor_gain':
      case 'contractor_loss':
        return (
          <div className="space-y-2">
            <Label htmlFor="amount" className="text-sm font-medium text-gunmetal">
              Monthly Cost ($)
            </Label>
            <Input
              id="amount"
              type="number"
              placeholder="5000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-white/50 border-gunmetal/20"
            />
          </div>
        );

      case 'increased_expense':
      case 'decreased_expense':
        return (
          <div className="space-y-2">
            <Label htmlFor="percentage" className="text-sm font-medium text-gunmetal">
              Change (%)
            </Label>
            <Select value={percentage} onValueChange={setPercentage}>
              <SelectTrigger className="bg-white/50 border-gunmetal/20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10%</SelectItem>
                <SelectItem value="25">25%</SelectItem>
                <SelectItem value="50">50%</SelectItem>
                <SelectItem value="100">100%</SelectItem>
              </SelectContent>
            </Select>
          </div>
        );

      case 'client_loss':
      case 'client_gain':
        return (
          <div className="space-y-2">
            <Label htmlFor="revenue" className="text-sm font-medium text-gunmetal">
              Monthly Revenue ($)
            </Label>
            <Input
              id="revenue"
              type="number"
              placeholder="10000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-white/50 border-gunmetal/20"
            />
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-[600px] bg-background">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-gunmetal">
            Build Manual Scenario
          </DialogTitle>
          <DialogDescription>
            Create a custom scenario to see how it impacts your forecast.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 pt-4">
          {/* Core fields */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Scenario Name */}
            <div className="space-y-2">
              <Label htmlFor="scenario-name" className="text-sm font-medium text-gunmetal">
                Scenario Name
              </Label>
              <Input
                id="scenario-name"
                type="text"
                placeholder="e.g., Client Loss Scenario"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={50}
                className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
              />
            </div>

            {/* Scenario Type */}
            <div className="space-y-2">
              <Label htmlFor="scenario-type" className="text-sm font-medium text-gunmetal">
                Scenario Type
              </Label>
              <Select
                value={type}
                onValueChange={(v) => setType(v as ScenarioType)}
              >
                <SelectTrigger className="bg-white/50 border-gunmetal/20 w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {SCENARIO_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Effective Date */}
            <div className="space-y-2">
              <Label htmlFor="effective-date" className="text-sm font-medium text-gunmetal">
                Effective Date
              </Label>
              <Input
                id="effective-date"
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="bg-white/50 border-gunmetal/20 focus:border-gunmetal"
              />
            </div>

            {/* Type-specific fields */}
            {renderTypeFields()}
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gunmetal/10">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isBuilding}
              className="border-gunmetal/20 text-gunmetal hover:bg-white/50"
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleBuild}
              disabled={!isValid || isBuilding}
              className="bg-gunmetal hover:bg-gunmetal/90 text-white"
            >
              {isBuilding ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Building...
                </>
              ) : (
                'Build & Apply'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
