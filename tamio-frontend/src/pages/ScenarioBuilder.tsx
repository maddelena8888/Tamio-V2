import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ModeToggle, SuggestedMode, ManualMode, type BuilderMode, type ManualScenarioParams } from '@/components/scenarios';
import { useTAMIPageContext } from '@/contexts/TAMIContext';

// Helper function to get display labels for entity values
const getLabel = (value: string): string => {
  const labels: Record<string, string> = {
    'retailco-rebrand': 'RetailCo Rebrand',
    'retailco': 'RetailCo',
    'techcorp': 'TechCorp',
    'healthtech': 'HealthTech Campaign',
    'product-designer': 'Product Designer',
    'senior-developer': 'Senior Developer',
    'sales-rep': 'Sales Rep',
    'aws': 'AWS',
    'marketing': 'Marketing',
    'software': 'Software',
    'figma': 'Figma',
    'office': 'Office lease',
  };
  return labels[value] || value;
};

// Helper function to format salary for display
const formatSalary = (salary: string): string => {
  const num = parseInt(salary, 10);
  return `$${(num / 1000).toFixed(0)}K/yr`;
};

/**
 * ScenarioBuilder - New streamlined scenario creation page.
 *
 * Two modes:
 * - Suggested: AI-generated Mad Libs style scenarios based on alerts/data
 * - Manual: User builds custom scenario from scratch
 *
 * Phase 1: Uses mock data, no backend integration.
 */
export default function ScenarioBuilder() {
  const [mode, setMode] = useState<BuilderMode>('suggested');
  const navigate = useNavigate();

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'scenario-builder',
    pageData: {
      builderMode: mode,
    },
  });

  const handleSimulate = useCallback(
    (params: Record<string, string>) => {
      const { scenarioType, scenarioId, ...variables } = params;

      // Build scenario name based on type
      let name = '';
      switch (scenarioType) {
        case 'payment_delay_in':
          name = `${getLabel(variables.client)} pays ${variables.days} days late`;
          break;
        case 'hiring':
          name = `Hire ${getLabel(variables.role)} at ${formatSalary(variables.salary)}`;
          break;
        case 'increased_expense':
          name = `${getLabel(variables.expense)} increases ${variables.percentage}%`;
          break;
        case 'client_loss':
          name = `Lose ${getLabel(variables.client)} as client`;
          break;
        case 'payment_delay_out':
          name = `Delay ${getLabel(variables.vendor)} payment by ${variables.days} days`;
          break;
        default:
          name = 'Custom Scenario';
      }

      toast.success('Scenario created!', {
        description: 'Redirecting to forecast view...',
      });

      // Build query string with standardized format
      const searchParams = new URLSearchParams({
        scenarioType,
        name,
        ...variables,
      });

      // Redirect to forecast page with scenario parameters
      setTimeout(() => {
        navigate(`/forecast?${searchParams.toString()}`);
      }, 500);
    },
    [navigate]
  );

  const handleBuild = useCallback(
    (scenarioParams: ManualScenarioParams) => {
      console.log('Building scenario with params:', scenarioParams);

      toast.success('Scenario created!', {
        description: `${scenarioParams.name} - Redirecting to forecast view...`,
      });

      // Build query string for redirect including type-specific params
      const searchParams = new URLSearchParams({
        name: scenarioParams.name,
        type: scenarioParams.type,
        date: scenarioParams.effectiveDate,
        params: JSON.stringify(scenarioParams.params),
      });

      // Redirect to forecast page with scenario parameters
      setTimeout(() => {
        navigate(`/forecast?${searchParams.toString()}`);
      }, 500);
    },
    [navigate]
  );

  const handleCancel = useCallback(() => {
    // Reset form - handled internally by ManualMode
    toast.info('Form cleared');
  }, []);

  return (
    <div className="relative min-h-[calc(100vh-8rem)] px-4 py-8">
      {/* Mode toggle - positioned at top right corner of page */}
      <div className="absolute top-4 right-4 z-10">
        <ModeToggle mode={mode} onModeChange={setMode} />
      </div>

      {/* Centered content */}
      <div className="flex items-center justify-center min-h-[calc(100vh-8rem)]">
        <div className="w-full max-w-[800px] mx-auto">
          {/* Main content card */}
          {mode === 'suggested' ? (
            <div
              className="
                bg-gradient-to-br from-tomato/5 via-white/60 to-white/40
                rounded-3xl
                p-12
                border-[3px] border-tomato/20
                shadow-[0_8px_32px_rgba(255,79,63,0.15),0_4px_16px_rgba(0,0,0,0.05)]
              "
            >
              <SuggestedMode onSimulate={handleSimulate} />
            </div>
          ) : (
            <div
              className="
                bg-white/40 backdrop-blur-md
                rounded-2xl
                p-8
                border border-white/20
                shadow-lg
              "
            >
              <ManualMode onBuild={handleBuild} onCancel={handleCancel} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
