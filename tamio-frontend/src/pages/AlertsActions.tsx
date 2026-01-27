/**
 * Alerts & Actions Page - Decision Queue Model
 *
 * Redesigned layout with three collapsible sections:
 * 1. Requires Your Decision (expanded by default) - Combined alert + recommendation cards
 * 2. Being Handled (collapsed) - Active mitigations in progress
 * 3. Monitoring (collapsed) - FYI items that don't need immediate action
 *
 * Features:
 * - Summary bar with counts at top
 * - Collapsible sections with smooth animations
 * - Combined DecisionCard showing alert + TAMI recommendation
 * - Action buttons: Approve, Modify, Dismiss
 */

import { useState, useCallback } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

import {
  AlertsActionsProvider,
  useAlertsActions,
} from '@/contexts/AlertsActionsContext';

import {
  TammyDrawer,
  RiskDetailModal,
  ControlDetailModal,
} from '@/components/alerts-actions';

import { DecisionQueueSummaryBar } from '@/components/alerts-actions/DecisionQueueSummaryBar';
import { DecisionQueueSection } from '@/components/alerts-actions/DecisionQueueSection';
import { DecisionCard } from '@/components/alerts-actions/DecisionCard';
import { BeingHandledCard } from '@/components/alerts-actions/BeingHandledCard';
import { MonitoringCard } from '@/components/alerts-actions/MonitoringCard';

import type { Risk, Control, DecisionItem } from '@/lib/api/alertsActions';
import { dismissRisk, approveControl } from '@/lib/api/alertsActions';

// ============================================================================
// Main Page Content (uses context)
// ============================================================================

function AlertsActionsContent() {
  const {
    isLoading,
    error,
    decisionQueueSummary,
    requiresDecisionItems,
    beingHandledItems,
    monitoringItems,
    riskControlMap,
    controlRiskMap,
    isTammyOpen,
    tammyPreloadedRisk,
    tammySessionId,
    openTammyWithRisk,
    closeTammy,
    setTammySessionId,
    refreshData,
    getRiskById,
    getControlById,
  } = useAlertsActions();

  // Modal state
  const [detailRisk, setDetailRisk] = useState<Risk | null>(null);
  const [detailControl, setDetailControl] = useState<Control | null>(null);

  // Handle approve action
  const handleApproveAction = useCallback(
    async (controlId: string) => {
      try {
        await approveControl(controlId);
        toast.success('Action approved');
        refreshData();
      } catch {
        toast.error('Failed to approve action');
      }
    },
    [refreshData]
  );

  // Handle dismiss risk
  const handleDismissRisk = useCallback(
    async (riskId: string) => {
      try {
        await dismissRisk(riskId);
        toast.success('Alert dismissed');
        refreshData();
      } catch {
        toast.error('Failed to dismiss alert');
      }
    },
    [refreshData]
  );

  // Handle modify (opens detail modal)
  const handleModify = useCallback(
    (item: DecisionItem) => {
      const risk = getRiskById(item.alert.id);
      if (risk) {
        setDetailRisk(risk);
      }
    },
    [getRiskById]
  );

  // Handle view details for Being Handled items
  const handleViewDetails = useCallback(
    (item: DecisionItem) => {
      const risk = getRiskById(item.alert.id);
      if (risk) {
        setDetailRisk(risk);
      }
    },
    [getRiskById]
  );

  // Handle chat with TAMI
  const handleChatWithTami = useCallback(
    (item: DecisionItem) => {
      const risk = getRiskById(item.alert.id);
      if (risk) {
        openTammyWithRisk(risk);
      }
    },
    [getRiskById, openTammyWithRisk]
  );

  // Get linked controls/risks for modals
  const getLinkedControlsForRisk = (risk: Risk): Control[] => {
    return (riskControlMap.get(risk.id) || [])
      .map((id) => getControlById(id))
      .filter(Boolean) as Control[];
  };

  const getLinkedRisksForControl = (control: Control): Risk[] => {
    return (controlRiskMap.get(control.id) || [])
      .map((id) => getRiskById(id))
      .filter(Boolean) as Risk[];
  };

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[400px] text-center">
        <AlertCircle className="w-10 h-10 text-tomato mb-4" />
        <h3 className="text-lg font-semibold text-gunmetal mb-2">
          Failed to load data
        </h3>
        <p className="text-sm text-gray-500 mb-4">{error}</p>
        <Button onClick={refreshData} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gunmetal">Alerts & Actions</h1>
          <p className="text-sm text-gray-500 mt-1">
            Review risks requiring decisions and track active mitigations
          </p>
        </div>

        {/* Summary Bar */}
        <div className="mb-6">
          <DecisionQueueSummaryBar
            summary={decisionQueueSummary}
            isLoading={isLoading}
            onRefresh={refreshData}
          />
        </div>

        {/* Decision Queue Sections */}
        <div className="space-y-4">
          {/* Section 1: Requires Your Decision (EXPANDED by default) */}
          <DecisionQueueSection
            title="Requires Your Decision"
            dotColor="red"
            count={requiresDecisionItems.length}
            defaultOpen={true}
            emptyMessage="No items requiring your decision"
          >
            {requiresDecisionItems.map((item) => (
              <DecisionCard
                key={item.id}
                item={item}
                onApprove={handleApproveAction}
                onModify={handleModify}
                onDismiss={handleDismissRisk}
                onChatWithTami={handleChatWithTami}
              />
            ))}
          </DecisionQueueSection>

          {/* Section 2: Being Handled (COLLAPSED by default) */}
          <DecisionQueueSection
            title="Being Handled"
            dotColor="blue"
            count={beingHandledItems.length}
            defaultOpen={false}
            emptyMessage="No mitigations currently executing"
          >
            {beingHandledItems.map((item) => (
              <BeingHandledCard
                key={item.id}
                item={item}
                onViewDetails={handleViewDetails}
              />
            ))}
          </DecisionQueueSection>

          {/* Section 3: Monitoring (COLLAPSED by default) */}
          <DecisionQueueSection
            title="Monitoring"
            dotColor="green"
            count={monitoringItems.length}
            defaultOpen={false}
            emptyMessage="No items to monitor"
          >
            {monitoringItems.map((item) => (
              <MonitoringCard
                key={item.id}
                item={item}
                onViewDetails={handleViewDetails}
              />
            ))}
          </DecisionQueueSection>
        </div>
      </div>

      {/* Tammy Drawer */}
      <TammyDrawer
        isOpen={isTammyOpen}
        onClose={closeTammy}
        preloadedRisk={tammyPreloadedRisk}
        sessionId={tammySessionId}
        onSessionCreate={setTammySessionId}
      />

      {/* Risk Detail Modal (for Modify action) */}
      <RiskDetailModal
        risk={detailRisk}
        linkedControls={detailRisk ? getLinkedControlsForRisk(detailRisk) : []}
        onClose={() => setDetailRisk(null)}
        onReviewWithTammy={() => {
          if (detailRisk) {
            setDetailRisk(null);
            openTammyWithRisk(detailRisk);
          }
        }}
        onDismiss={async () => {
          if (detailRisk) {
            await handleDismissRisk(detailRisk.id);
            setDetailRisk(null);
          }
        }}
        onControlClick={(control) => {
          setDetailRisk(null);
          setDetailControl(control);
        }}
        onAddCustomAction={() => {
          if (detailRisk) {
            setDetailRisk(null);
            openTammyWithRisk(detailRisk);
          }
        }}
        onControlUpdated={refreshData}
      />

      {/* Control Detail Modal */}
      <ControlDetailModal
        control={detailControl}
        linkedRisks={
          detailControl ? getLinkedRisksForControl(detailControl) : []
        }
        onClose={() => setDetailControl(null)}
        onRiskClick={(risk) => {
          setDetailControl(null);
          setDetailRisk(risk);
        }}
        onControlUpdated={refreshData}
      />
    </div>
  );
}

// ============================================================================
// Page Wrapper with Provider
// ============================================================================

export default function AlertsActionsPage() {
  return (
    <AlertsActionsProvider>
      <AlertsActionsContent />
    </AlertsActionsProvider>
  );
}
