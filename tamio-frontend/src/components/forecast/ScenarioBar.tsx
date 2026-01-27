import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, X, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ScenarioType } from '@/lib/api/types';

// ============================================================================
// Scenario Parameter Configuration
// ============================================================================

interface ParameterOption {
  value: string;
  label: string;
}

interface ParameterConfig {
  key: string;
  label: string;
  options: ParameterOption[];
}

const SCENARIO_PARAMETERS: Record<ScenarioType, ParameterConfig[]> = {
  payment_delay_in: [
    {
      key: 'client',
      label: 'Client',
      options: [
        { value: 'retailco-rebrand', label: 'RetailCo Rebrand' },
        { value: 'techcorp', label: 'TechCorp' },
        { value: 'healthtech', label: 'HealthTech Campaign' },
      ],
    },
    {
      key: 'days',
      label: 'Delay',
      options: [
        { value: '14', label: '14 days' },
        { value: '30', label: '30 days' },
        { value: '60', label: '60 days' },
        { value: '90', label: '90 days' },
      ],
    },
  ],
  payment_delay_out: [
    {
      key: 'vendor',
      label: 'Vendor',
      options: [
        { value: 'aws', label: 'AWS' },
        { value: 'figma', label: 'Figma' },
        { value: 'office', label: 'Office lease' },
      ],
    },
    {
      key: 'days',
      label: 'Delay',
      options: [
        { value: '15', label: '15 days' },
        { value: '30', label: '30 days' },
        { value: '45', label: '45 days' },
      ],
    },
  ],
  hiring: [
    {
      key: 'role',
      label: 'Role',
      options: [
        { value: 'product-designer', label: 'Product Designer' },
        { value: 'senior-developer', label: 'Senior Developer' },
        { value: 'sales-rep', label: 'Sales Rep' },
      ],
    },
    {
      key: 'date',
      label: 'Start Date',
      options: [
        { value: '2026-03-01', label: 'March 1st' },
        { value: '2026-04-01', label: 'April 1st' },
        { value: '2026-05-01', label: 'May 1st' },
      ],
    },
    {
      key: 'salary',
      label: 'Salary',
      options: [
        { value: '60000', label: '$60,000/yr' },
        { value: '85000', label: '$85,000/yr' },
        { value: '100000', label: '$100,000/yr' },
        { value: '120000', label: '$120,000/yr' },
      ],
    },
  ],
  firing: [],
  client_loss: [
    {
      key: 'client',
      label: 'Client',
      options: [
        { value: 'techcorp', label: 'TechCorp' },
        { value: 'retailco', label: 'RetailCo' },
        { value: 'healthtech', label: 'HealthTech Campaign' },
      ],
    },
  ],
  client_gain: [],
  client_change: [],
  contractor_gain: [],
  contractor_loss: [],
  increased_expense: [
    {
      key: 'expense',
      label: 'Expense',
      options: [
        { value: 'aws', label: 'AWS Infrastructure' },
        { value: 'marketing', label: 'Marketing spend' },
        { value: 'software', label: 'Software subscriptions' },
      ],
    },
    {
      key: 'percentage',
      label: 'Increase',
      options: [
        { value: '15', label: '15%' },
        { value: '25', label: '25%' },
        { value: '50', label: '50%' },
      ],
    },
  ],
  decreased_expense: [],
};

// Helper to get label from value
function getOptionLabel(options: ParameterOption[], value: string): string {
  const option = options.find(o => o.value === value);
  return option?.label || value;
}

// ============================================================================
// Props Interface
// ============================================================================

interface ScenarioBarProps {
  scenarioActive: boolean;
  scenarioName?: string | null;
  impactStatement?: string | null;
  scenarioType?: ScenarioType | null;
  scenarioParams?: Record<string, string>;
  onParamChange?: (key: string, value: string) => void;
  onClearScenario?: () => void;
  onShare?: () => void;
  onSecondOrderEffects?: () => void;
  className?: string;
}

export function ScenarioBar({
  scenarioActive,
  scenarioName,
  impactStatement,
  scenarioType,
  scenarioParams,
  onParamChange,
  onClearScenario,
  onShare,
  onSecondOrderEffects,
  className,
}: ScenarioBarProps) {
  const navigate = useNavigate();

  const handleAddNewScenario = () => {
    navigate('/scenarios');
  };

  // Get editable parameters for current scenario type
  const editableParams = scenarioType ? SCENARIO_PARAMETERS[scenarioType] : [];
  const hasEditableParams = editableParams.length > 0 && scenarioParams && onParamChange;

  return (
    <div
      className={cn(
        'w-full rounded-2xl p-6',
        'bg-white/40 backdrop-blur-md',
        'border border-white/20',
        'shadow-lg shadow-black/5',
        className
      )}
    >
      {/* Scenario Title & Editable Parameters (when active) */}
      {scenarioActive && scenarioName && (
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gunmetal">
            Scenario: "{scenarioName}"
          </h2>

          {/* Editable Parameters */}
          {hasEditableParams ? (
            <div className="flex flex-wrap items-center gap-3 mt-3">
              {editableParams.map((param) => {
                const currentValue = scenarioParams[param.key] || '';
                return (
                  <Select
                    key={param.key}
                    value={currentValue}
                    onValueChange={(value) => onParamChange(param.key, value)}
                  >
                    <SelectTrigger
                      className="
                        inline-flex h-9 px-4 gap-2
                        bg-white/90 hover:bg-white
                        border border-gunmetal/20 hover:border-gunmetal/40
                        text-sm font-medium text-gunmetal
                        rounded-full
                        shadow-sm hover:shadow
                        transition-all duration-150
                        w-auto min-w-0
                        [&>svg]:h-4 [&>svg]:w-4 [&>svg]:opacity-50
                      "
                    >
                      <span className="text-gunmetal/50 font-normal">{param.label}:</span>
                      <SelectValue>
                        {getOptionLabel(param.options, currentValue)}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {param.options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                );
              })}
            </div>
          ) : impactStatement ? (
            <p className="text-sm text-gunmetal/80 mt-1">
              Impact: {impactStatement}
            </p>
          ) : null}
        </div>
      )}

      {/* Buttons Row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {!scenarioActive ? (
            <Button
              variant="outline"
              onClick={handleAddNewScenario}
              className="bg-transparent border-2 border-gunmetal text-gunmetal hover:bg-gunmetal hover:text-white"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add New Scenario
            </Button>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={onSecondOrderEffects}
                className="bg-transparent border-2 border-gunmetal text-gunmetal hover:bg-gunmetal hover:text-white"
              >
                <Plus className="h-4 w-4 mr-2" />
                Second Order Effects
              </Button>
              <Button
                variant="outline"
                onClick={onClearScenario}
                className="bg-transparent border-2 border-gunmetal text-gunmetal hover:bg-gunmetal hover:text-white"
              >
                <X className="h-4 w-4 mr-2" />
                Clear Scenario
              </Button>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={onShare}
            className="bg-gunmetal text-white hover:bg-gunmetal/90"
          >
            <Share2 className="h-4 w-4 mr-2" />
            Share
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ScenarioBar;
