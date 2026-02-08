import { useEffect, useState, useMemo } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { getForecast } from '@/lib/api/forecast';
import { ScenarioToggle } from '@/components/projections/ScenarioToggle';
import { ProjectionsTable } from '@/components/projections/ProjectionsTable';
import { transformForecastToProjections } from '@/components/projections/types';
import type { ForecastResponse } from '@/lib/api/types';
import type { ScenarioView, ProjectionsTableData } from '@/components/projections/types';

export default function Projections() {
  const { user } = useAuth();

  // Data state
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // View state
  const [scenarioView, setScenarioView] = useState<ScenarioView>('expected');

  // Register TAMI page context
  useTAMIPageContext({
    page: 'projections',
    pageData: {
      scenarioView,
    },
  });

  // Fetch forecast data
  const fetchData = async () => {
    if (!user?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      const forecastData = await getForecast(user.id, 13); // 13 weeks = ~3 months
      setForecast(forecastData);
    } catch (err) {
      console.error('Error fetching forecast:', err);
      setError('Failed to load projection data. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [user?.id]);

  // Transform forecast data to table format
  const tableData: ProjectionsTableData | null = useMemo(() => {
    if (!forecast) return null;
    return transformForecastToProjections(forecast, 9); // W0-W8 (9 weeks)
  }, [forecast]);

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gunmetal">Projections</h1>
        </div>
        <NeuroCard className="p-8 text-center">
          <AlertTriangle className="w-12 h-12 mx-auto text-amber-500 mb-4" />
          <h3 className="text-lg font-semibold mb-2">Failed to load projections</h3>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Button onClick={fetchData}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </NeuroCard>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gunmetal">Projections</h1>
          <p className="text-sm text-muted-foreground mt-1">
            View your cash flow forecast by week
          </p>
        </div>
        <ScenarioToggle value={scenarioView} onChange={setScenarioView} />
      </div>

      {/* Main Table */}
      <ProjectionsTable
        data={tableData}
        scenarioView={scenarioView}
        isLoading={isLoading}
      />

      {/* Legend */}
      {!isLoading && tableData && (
        <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-lime" />
            <span>Income</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tomato" />
            <span>Costs</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-lime-dark" />
            <span>High confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Medium confidence</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-tomato" />
            <span>Low confidence</span>
          </div>
        </div>
      )}
    </div>
  );
}
