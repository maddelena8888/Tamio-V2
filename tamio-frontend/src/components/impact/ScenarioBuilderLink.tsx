import { Link } from 'react-router-dom';

interface ScenarioBuilderLinkProps {
  alertId?: string;
}

export function ScenarioBuilderLink({ alertId }: ScenarioBuilderLinkProps) {
  // Pass alert context to scenario builder via URL params
  const scenarioUrl = alertId
    ? `/scenarios?alertId=${alertId}`
    : '/scenarios';

  return (
    <div className="text-center mt-8">
      <p className="text-gunmetal/70">
        None of these work?{' '}
        <Link
          to={scenarioUrl}
          className="text-gunmetal underline underline-offset-2 hover:text-gunmetal/80 transition-colors"
        >
          Open Scenario Builder
        </Link>
        {' '}to find another way
      </p>
    </div>
  );
}
