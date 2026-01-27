import { useState, useCallback } from 'react';
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
import { SCENARIO_TYPE_OPTIONS, type ScenarioType } from './mockData';
import { ScenarioTypeFields, type AnyScenarioParams } from './fields';

export interface ManualScenarioParams {
  name: string;
  type: ScenarioType;
  effectiveDate: string;
  params: AnyScenarioParams;
}

interface ManualModeProps {
  onBuild: (params: ManualScenarioParams) => void;
  onCancel: () => void;
}

export function ManualMode({ onBuild, onCancel }: ManualModeProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState<ScenarioType | ''>('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [typeParams, setTypeParams] = useState<Partial<AnyScenarioParams>>({});

  const handleTypeChange = useCallback((newType: ScenarioType) => {
    setType(newType);
    setTypeParams({}); // Reset params when type changes
  }, []);

  const handleBuild = useCallback(() => {
    if (!name || !type || !effectiveDate) return;
    onBuild({
      name,
      type: type as ScenarioType,
      effectiveDate,
      params: typeParams as AnyScenarioParams,
    });
  }, [name, type, effectiveDate, typeParams, onBuild]);

  const handleCancel = useCallback(() => {
    setName('');
    setType('');
    setEffectiveDate('');
    setTypeParams({});
    onCancel();
  }, [onCancel]);

  // Basic validation - name and type required, effectiveDate included for reference
  const isValid = name.trim() && type && effectiveDate;

  return (
    <div className="w-full">
      {/* Header */}
      <h2 className="text-xl font-semibold text-gunmetal mb-6">
        Test Your Own Scenario
      </h2>

      {/* Form fields in horizontal layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Scenario Name */}
        <div className="space-y-2">
          <Label htmlFor="scenario-name" className="text-sm font-medium text-gunmetal">
            Scenario Name
          </Label>
          <Input
            id="scenario-name"
            type="text"
            placeholder="Client Loss Scenario"
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
          <Select value={type} onValueChange={(v) => handleTypeChange(v as ScenarioType)}>
            <SelectTrigger
              id="scenario-type"
              className="bg-white/50 border-gunmetal/20 focus:border-gunmetal w-full"
            >
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
      </div>

      {/* Type-specific fields */}
      {type && (
        <div className="mb-6 p-4 bg-white/30 rounded-lg border border-gunmetal/10">
          <h3 className="text-sm font-medium text-gunmetal mb-4">Scenario Details</h3>
          <ScenarioTypeFields
            scenarioType={type}
            params={typeParams}
            onChange={setTypeParams}
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={handleCancel}
          className="
            px-6 py-2
            bg-transparent
            border border-gunmetal/20
            text-gunmetal
            hover:bg-white/50
            rounded-lg
          "
        >
          Cancel
        </Button>
        <Button
          type="button"
          onClick={handleBuild}
          disabled={!isValid}
          className="
            px-6 py-2
            bg-gunmetal hover:bg-gunmetal/90
            text-white font-semibold
            rounded-lg
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Build Scenario
        </Button>
      </div>
    </div>
  );
}
