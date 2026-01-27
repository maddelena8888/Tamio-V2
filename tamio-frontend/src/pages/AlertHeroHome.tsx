import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AlertHeroCard, EmptyAlertState } from '@/components/home';
import { getHighestPriorityAlert, type Risk } from '@/lib/api/alertsActions';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useTAMIPageContext } from '@/contexts/TAMIContext';

/**
 * AlertHeroHome - New streamlined home page that displays the highest priority alert.
 *
 * This page replaces the complex dashboard with a focused alert-first experience.
 * Users see the single most critical alert with clear action paths:
 * - "View Impact" button navigates to the impact visualization
 * - "View other alerts" link navigates to the full alerts list
 */
export default function AlertHeroHome() {
  const [alert, setAlert] = useState<Risk | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'alerts-home',
    pageData: alert
      ? {
          currentAlert: {
            id: alert.id,
            title: alert.title,
            severity: alert.severity,
          },
        }
      : undefined,
  });

  useEffect(() => {
    async function fetchHighestPriorityAlert() {
      try {
        setIsLoading(true);
        setError(null);
        const highestPriority = await getHighestPriorityAlert();
        setAlert(highestPriority);
      } catch (err) {
        console.error('Failed to fetch highest priority alert:', err);
        setError('Failed to load alerts');
      } finally {
        setIsLoading(false);
      }
    }

    fetchHighestPriorityAlert();
  }, []);

  const handleViewImpact = () => {
    if (alert) {
      navigate(`/alerts/${alert.id}/impact`);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-8rem)]">
        <LoadingSkeleton />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-8rem)]">
        <p className="text-lg text-muted-foreground mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="text-sm text-gunmetal hover:text-gunmetal/80 underline"
        >
          Try again
        </button>
      </div>
    );
  }

  // Empty state - no alerts
  if (!alert) {
    return <EmptyAlertState />;
  }

  // Main state - show alert hero card
  return (
    <div className="relative min-h-[calc(100vh-8rem)] px-4">
      {/* View Other Alerts - Top Right */}
      <Button variant="outline" asChild className="absolute -top-4 right-0">
        <Link to="/action-monitor">
          View other alerts &rarr;
        </Link>
      </Button>

      {/* Centered Alert Card */}
      <div className="flex items-center justify-center min-h-[calc(100vh-8rem)]">
        <AlertHeroCard alert={alert} onViewImpact={handleViewImpact} />
      </div>
    </div>
  );
}

/**
 * Loading skeleton that matches the AlertHeroCard dimensions
 */
function LoadingSkeleton() {
  return (
    <div className="w-full max-w-[800px] mx-auto p-16 rounded-3xl bg-white/30 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-6">
        <Skeleton className="h-8 w-[350px]" />
        <Skeleton className="h-6 w-[450px]" />
        <Skeleton className="h-6 w-[400px]" />
        <Skeleton className="h-12 w-[200px] mt-4" />
        <Skeleton className="h-4 w-[120px]" />
      </div>
    </div>
  );
}
