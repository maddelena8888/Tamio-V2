import { useState, useMemo, useCallback, Fragment, type ReactNode } from 'react';
import { RefreshCw, Info } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { MOCK_SUGGESTED_SCENARIOS, type MockSuggestedScenario } from './mockData';

interface SuggestedModeProps {
  onSimulate: (params: Record<string, string>) => void;
}

export function SuggestedMode({ onSimulate }: SuggestedModeProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedValues, setSelectedValues] = useState<Record<string, string>>({});

  const currentScenario = MOCK_SUGGESTED_SCENARIOS[currentIndex];

  // Initialize selected values when scenario changes
  const effectiveValues = useMemo(() => {
    const defaults: Record<string, string> = {};
    currentScenario.variables.forEach((v) => {
      defaults[v.key] = selectedValues[v.key] || v.defaultValue;
    });
    return defaults;
  }, [currentScenario, selectedValues]);

  const handleRefresh = useCallback(() => {
    const nextIndex = (currentIndex + 1) % MOCK_SUGGESTED_SCENARIOS.length;
    setCurrentIndex(nextIndex);
    setSelectedValues({}); // Reset selections for new scenario
  }, [currentIndex]);

  const handleValueChange = useCallback((key: string, value: string) => {
    setSelectedValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSimulate = useCallback(() => {
    onSimulate({
      scenarioType: currentScenario.scenarioType,
      scenarioId: currentScenario.id,
      ...effectiveValues,
    });
  }, [currentScenario, effectiveValues, onSimulate]);

  // Parse template and render with inline dropdowns
  const renderedTemplate = useMemo(() => {
    return parseAndRenderTemplate(
      currentScenario,
      effectiveValues,
      handleValueChange
    );
  }, [currentScenario, effectiveValues, handleValueChange]);

  return (
    <div className="flex flex-col items-center">
      {/* Info and Refresh buttons - centered above text */}
      <div className="w-full flex justify-center gap-2 mb-6">
        {currentScenario.reason && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="p-2 rounded-full text-gunmetal/60 hover:text-gunmetal hover:bg-white/30 transition-colors"
                aria-label="Why this scenario?"
              >
                <Info className="size-5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs">
              {currentScenario.reason}
            </TooltipContent>
          </Tooltip>
        )}
        <button
          type="button"
          onClick={handleRefresh}
          className="p-2 rounded-full text-gunmetal/60 hover:text-gunmetal hover:bg-white/30 transition-colors"
          aria-label="Show different scenario"
        >
          <RefreshCw className="size-5" />
        </button>
      </div>

      {/* Mad Libs sentence */}
      <div className="text-center mb-10 px-2">
        <p className="text-2xl sm:text-[28px] md:text-[32px] leading-snug md:leading-relaxed text-gunmetal font-medium text-balance">
          {renderedTemplate}
        </p>
      </div>

      {/* Simulate button */}
      <Button
        onClick={handleSimulate}
        className="
          h-12 px-8
          bg-tomato/15 hover:bg-tomato/25
          text-gunmetal font-semibold
          rounded-full
          border-2 border-tomato/30
          shadow-md hover:shadow-lg
          transition-all duration-200
        "
      >
        Simulate Impact
      </Button>
    </div>
  );
}

function parseAndRenderTemplate(
  scenario: MockSuggestedScenario,
  values: Record<string, string>,
  onChange: (key: string, value: string) => void
) {
  const { template, variables } = scenario;
  const parts: (string | ReactNode)[] = [];

  // Regex to match {variableKey}
  const regex = /\{(\w+)\}/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(template)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      parts.push(template.slice(lastIndex, match.index));
    }

    const key = match[1];
    const variable = variables.find((v) => v.key === key);

    if (variable) {
      const currentValue = values[key] || variable.defaultValue;
      const selectedOption = variable.options.find((o) => o.value === currentValue);

      parts.push(
        <InlineSelect
          key={`${scenario.id}-${key}`}
          options={variable.options}
          value={currentValue}
          displayValue={selectedOption?.label || currentValue}
          onChange={(value) => onChange(key, value)}
        />
      );
    } else {
      // Variable not found, render as text
      parts.push(match[0]);
    }

    lastIndex = regex.lastIndex;
  }

  // Add remaining text
  if (lastIndex < template.length) {
    parts.push(template.slice(lastIndex));
  }

  return parts.map((part, index) =>
    typeof part === 'string' ? <Fragment key={index}>{part}</Fragment> : part
  );
}

interface InlineSelectProps {
  options: { value: string; label: string }[];
  value: string;
  displayValue: string;
  onChange: (value: string) => void;
}

function InlineSelect({ options, value, displayValue, onChange }: InlineSelectProps) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        className="
          inline-flex h-auto px-0.5 py-0
          border-0 border-b-2 border-tomato/40
          bg-transparent
          text-2xl sm:text-[28px] md:text-[32px] font-medium text-gunmetal
          rounded-none
          shadow-none
          hover:border-tomato
          focus:ring-0 focus:border-tomato
          w-auto min-w-0
          [&>svg]:hidden
        "
      >
        <SelectValue>
          <span className="underline decoration-2 underline-offset-4 decoration-tomato/50">
            {displayValue}
          </span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
