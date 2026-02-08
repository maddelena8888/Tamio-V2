/**
 * Health Page - Customizable Dashboard
 *
 * A card-based dashboard where users can:
 * - Start from a preset view (Leader or Finance Manager)
 * - Add/remove cards from a widget library
 * - Drag-and-drop to reorder cards
 * - Configure individual card settings
 */

import { useTAMIPageContext } from '@/contexts/TAMIContext';
import { DashboardProvider, useDashboard } from '@/contexts/DashboardContext';
import { WidgetDataProvider, useWidgetData } from '@/hooks/useDashboardData';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Share, Plus, ChevronDown, Download, Copy, Shield, Users } from 'lucide-react';
import { NotificationsDropdown } from '@/components/notifications';
import { toast } from 'sonner';
import {
  DashboardGrid,
  ViewSwitcher,
  AddWidgetButton,
} from '@/components/dashboard';
import { AlertsPanelSection } from '@/components/dashboard/alerts-panel';

// Static collaborators for display (matching Home page)
const collaborators = [
  { id: '1', initials: 'JD', name: 'John Doe', color: '#7C3AED', online: true },
  { id: '2', initials: 'AK', name: 'Amy Kim', color: '#059669', online: true },
  { id: '3', initials: 'TS', name: 'Tom Smith', color: '#DC2626', online: false },
];

// ============================================================================
// Loading Skeleton
// ============================================================================

function DashboardSkeleton() {
  return (
    <div className="px-6 pt-4 max-w-[1400px] mx-auto">
      {/* Header skeleton */}
      <div className="flex items-center justify-between mb-6">
        <Skeleton className="h-8 w-32" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-[180px]" />
          <Skeleton className="h-10 w-28" />
        </div>
      </div>

      {/* Grid skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[250px] rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Error State
// ============================================================================

function ErrorState({ message }: { message: string }) {
  return (
    <div className="px-6 pt-4 max-w-[1400px] mx-auto flex items-center justify-center min-h-[400px]">
      <div className="rounded-2xl p-8 bg-tomato/10 border border-tomato/20 text-center max-w-md">
        <h2 className="text-xl font-bold text-tomato mb-2">
          Unable to Load Dashboard
        </h2>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

// ============================================================================
// Dashboard Content (inside providers)
// ============================================================================

function DashboardContent() {
  const { isLoading: contextLoading } = useDashboard();
  const { healthData, isLoading: dataLoading, error } = useWidgetData();

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'health',
    pageData: healthData
      ? {
          runway_weeks: healthData.runway.value,
          liquidity_ratio: healthData.liquidity.value,
          cash_velocity_days: healthData.cash_velocity.value,
          obligations_status: healthData.obligations_health.status,
          obligations_covered: healthData.obligations_health.covered_count,
          obligations_total: healthData.obligations_health.total_count,
          receivables_status: healthData.receivables_health.status,
          receivables_overdue: healthData.receivables_health.overdue_amount,
          critical_alerts_count: healthData.critical_alerts.length,
        }
      : undefined,
  });

  // Loading state
  if (contextLoading || dataLoading) {
    return <DashboardSkeleton />;
  }

  // Error state
  if (error) {
    return <ErrorState message={error} />;
  }

  const handleNotificationClick = (notification?: { id: string; title: string }) => {
    if (notification) {
      toast.info(`Opening: ${notification.title}`);
    }
  };

  const handleShareClick = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success('Link copied to clipboard');
    } catch {
      toast.error('Failed to copy link');
    }
  };

  const handleAddCollaborator = () => {
    toast.info('Collaboration features coming soon');
  };

  return (
    <div className="px-6 pt-4 max-w-[1400px] mx-auto pb-8 relative">
      {/* Header Controls - positioned top right, matching Home page */}
      <div className="fixed top-[32px] right-6 flex items-center gap-3 z-50">
        {/* Collaborators */}
        <div className="flex items-center">
          {collaborators.map((collab, i) => (
            <div
              key={collab.id}
              className="w-8 h-8 rounded-full border-2 border-white flex items-center justify-center text-xs font-semibold text-white cursor-pointer transition-transform hover:scale-110 hover:z-10 relative shadow-sm"
              style={{
                background: collab.color,
                marginLeft: i > 0 ? '-8px' : 0,
                zIndex: collaborators.length - i,
              }}
              title={collab.name}
            >
              {collab.initials}
              {collab.online && (
                <span className="absolute bottom-0 right-0 w-2 h-2 bg-lime-dark rounded-full border-2 border-white" />
              )}
            </div>
          ))}
          <button
            onClick={handleAddCollaborator}
            className="w-8 h-8 rounded-full border-2 border-dashed border-border bg-transparent text-muted-foreground flex items-center justify-center ml-1 cursor-pointer transition-all hover:border-lime-dark hover:text-lime-dark"
            title="Invite collaborator"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Notifications */}
        <NotificationsDropdown onNotificationClick={handleNotificationClick} />

        {/* Share Button with Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className="flex items-center gap-1.5 bg-gunmetal hover:bg-gunmetal/90 text-white"
              size="sm"
            >
              <Share className="w-4 h-4" />
              Share
              <ChevronDown className="w-3 h-3 ml-0.5 opacity-70" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64">
            <DropdownMenuItem
              onClick={() => toast.info('Share dialog coming soon')}
              className="flex flex-col items-start gap-0.5 py-2.5 cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-muted-foreground" />
                <span className="font-medium text-gunmetal">Share Dashboard</span>
              </div>
              <span className="text-[11px] text-muted-foreground pl-6">
                Invite team members to view or edit
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => toast.info('Export feature coming soon')}
              className="flex flex-col items-start gap-0.5 py-2.5 cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Download className="w-4 h-4 text-muted-foreground" />
                <span className="font-medium text-gunmetal">Export Snapshot</span>
              </div>
              <span className="text-[11px] text-muted-foreground pl-6">
                Download as PDF or image
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleShareClick}
              className="flex flex-col items-start gap-0.5 py-2.5 cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Copy className="w-4 h-4 text-muted-foreground" />
                <span className="font-medium text-gunmetal">Copy for Board Deck</span>
              </div>
              <span className="text-[11px] text-muted-foreground pl-6">
                Formatted summary for presentations
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => toast.info('Access management coming soon')}
              className="flex flex-col items-start gap-0.5 py-2.5 cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-muted-foreground" />
                <span className="font-medium text-gunmetal">Manage Access</span>
              </div>
              <span className="text-[11px] text-muted-foreground pl-6">
                See who has access to this dashboard
              </span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gunmetal">Dashboard</h1>
        <div className="flex items-center gap-3">
          <ViewSwitcher />
          <AddWidgetButton />
        </div>
      </div>

      {/* Dashboard Grid */}
      <DashboardGrid />

      {/* Alerts Panel */}
      <div className="mt-6">
        <AlertsPanelSection />
      </div>
    </div>
  );
}

// ============================================================================
// Main Component (with providers)
// ============================================================================

export default function Health() {
  return (
    <DashboardProvider>
      <WidgetDataProvider>
        <DashboardContent />
      </WidgetDataProvider>
    </DashboardProvider>
  );
}
