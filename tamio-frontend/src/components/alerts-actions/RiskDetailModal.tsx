/**
 * RiskDetailModal Component - V4 Risk/Controls Architecture
 *
 * Redesigned modal providing actionable value beyond the card:
 * - Plain-language summary
 * - Why it matters now (urgency/timing)
 * - Buffer impact with key numbers
 * - Suggested actions with approve/reject
 * - Prevention tips (collapsible)
 */

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  AlertCircle,
  Clock,
  DollarSign,
  TrendingDown,
  Shield,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  X,
  Check,
  Lightbulb,
  Plus,
  AlertTriangle,
  Loader2,
  ThumbsUp,
  ThumbsDown,
  Sparkles,
} from 'lucide-react';
import type { Risk, Control } from '@/lib/api/alertsActions';
import {
  getSeverityStyles,
  getControlStateStyles,
  approveControl,
  rejectControl,
} from '@/lib/api/alertsActions';
import { toast } from 'sonner';

interface RiskDetailModalProps {
  risk: Risk | null;
  linkedControls: Control[];
  onClose: () => void;
  onReviewWithTammy: () => void;
  onDismiss: () => void;
  onControlClick: (control: Control) => void;
  onAddCustomAction?: () => void;
  onControlUpdated?: () => void;
}

export function RiskDetailModal({
  risk,
  linkedControls,
  onClose,
  onReviewWithTammy,
  onDismiss,
  onControlClick,
  onAddCustomAction,
  onControlUpdated,
}: RiskDetailModalProps) {
  const [isPreventionOpen, setIsPreventionOpen] = useState(false);
  const [isRejectedOpen, setIsRejectedOpen] = useState(false);
  const [loadingControlId, setLoadingControlId] = useState<string | null>(null);

  if (!risk) return null;

  const severityStyles = getSeverityStyles(risk.severity);

  const formatAmount = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '--';
    const absValue = Math.abs(value);
    if (absValue >= 1000000) {
      return `$${(absValue / 1000000).toFixed(1)}M`;
    }
    if (absValue >= 1000) {
      return `$${Math.round(absValue / 1000)}K`;
    }
    return `$${absValue.toLocaleString()}`;
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });
  };

  // Get pending controls that need approval (suggested actions)
  const pendingControls = linkedControls.filter((c) => c.state === 'pending');
  const activeControls = linkedControls.filter((c) => c.state !== 'pending');

  // Get rejected suggestions from linked controls
  const rejectedSuggestions = linkedControls
    .flatMap((c) => c.rejected_suggestions || [])
    .filter(Boolean);

  // Generate plain-language summary from risk data
  const generateSummary = (): string => {
    const parts: string[] = [];

    if (risk.title) {
      parts.push(risk.title);
    }

    if (risk.primary_driver) {
      parts.push(`Likely cause: ${risk.primary_driver}`);
    }

    return parts.join('. ') || 'Review the details below for more information.';
  };

  // Handle approve action
  const handleApprove = async (control: Control) => {
    setLoadingControlId(control.id);
    try {
      await approveControl(control.id);
      toast.success(`"${control.name}" approved and activated`);
      onControlUpdated?.();
    } catch (error) {
      toast.error('Failed to approve action');
      console.error(error);
    } finally {
      setLoadingControlId(null);
    }
  };

  // Handle reject action
  const handleReject = async (control: Control) => {
    setLoadingControlId(control.id);
    try {
      await rejectControl(control.id, 'Rejected by user');
      toast.success(`"${control.name}" rejected`);
      onControlUpdated?.();
    } catch (error) {
      toast.error('Failed to reject action');
      console.error(error);
    } finally {
      setLoadingControlId(null);
    }
  };

  return (
    <Dialog open={!!risk} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto bg-white/95 backdrop-blur-md">
        {/* Header */}
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center',
                  severityStyles.bgClass
                )}
              >
                <AlertCircle className={cn('w-5 h-5', severityStyles.textClass)} />
              </div>
              <div className="flex-1">
                <DialogTitle className="text-base font-semibold text-gunmetal">
                  {risk.title}
                </DialogTitle>
                <p className="text-xs text-gray-500 mt-1">
                  Detected {formatDate(risk.detected_at)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {risk.due_horizon_label && risk.due_horizon_label !== 'No deadline' && (
                <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 text-xs text-gray-600">
                  <Clock className="w-3 h-3" />
                  {risk.due_horizon_label}
                </span>
              )}
              <span
                className={cn(
                  'px-2.5 py-1 rounded-full text-xs font-medium',
                  severityStyles.bgClass,
                  severityStyles.textClass
                )}
              >
                {risk.severity.charAt(0).toUpperCase() + risk.severity.slice(1)}
              </span>
            </div>
          </div>
        </DialogHeader>

        {/* Section 1: Plain-Language Summary */}
        <div className="py-4 border-b border-gray-100">
          <p className="text-sm text-gunmetal leading-relaxed">
            {generateSummary()}
          </p>
        </div>

        {/* Section 2: Why It Matters Now */}
        {risk.context_bullets.length > 0 && (
          <div className="py-4 border-b border-gray-100">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5" />
              Why It Matters Now
            </h4>
            <ul className="space-y-2">
              {risk.context_bullets.map((bullet, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 text-sm text-gray-600"
                >
                  <span className="text-gray-400 mt-0.5">•</span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Section 3: Buffer Impact */}
        <div className="py-4 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
            <TrendingDown className="w-3.5 h-3.5" />
            Impact
          </h4>
          <div className="grid grid-cols-2 gap-4">
            {/* Cash Impact */}
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <DollarSign className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-500">Cash Impact</span>
              </div>
              <p
                className={cn(
                  'text-xl font-bold',
                  risk.cash_impact && risk.cash_impact < 0
                    ? 'text-tomato'
                    : 'text-gunmetal'
                )}
              >
                {formatAmount(risk.cash_impact)}
              </p>
            </div>

            {/* Buffer Impact */}
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <TrendingDown className="w-4 h-4 text-gray-400" />
                <span className="text-xs text-gray-500">Buffer Impact</span>
              </div>
              <p className={cn(
                'text-xl font-bold',
                risk.buffer_impact_percent && risk.buffer_impact_percent > 50
                  ? 'text-tomato'
                  : risk.buffer_impact_percent && risk.buffer_impact_percent > 25
                  ? 'text-amber-600'
                  : 'text-gunmetal'
              )}>
                {risk.buffer_impact_percent
                  ? `${risk.buffer_impact_percent}%`
                  : '--'}
              </p>
              <p className="text-[10px] text-gray-400 mt-1">of your safety buffer</p>
            </div>
          </div>
        </div>

        {/* Section 4: Suggested Actions */}
        {pendingControls.length > 0 && (
          <div className="py-4 border-b border-gray-100">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5" />
              Suggested Actions
            </h4>
            <p className="text-xs text-gray-500 mb-3">
              Tamio has prepared these interventions for your review:
            </p>
            <div className="space-y-3">
              {pendingControls.map((control, idx) => {
                const isLoading = loadingControlId === control.id;
                return (
                  <div
                    key={control.id}
                    className={cn(
                      'p-4 rounded-lg border transition-all',
                      idx === 0
                        ? 'bg-lime/5 border-lime/30'
                        : 'bg-gray-50 border-gray-200'
                    )}
                  >
                    {idx === 0 && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-lime/20 text-lime-700 text-[10px] font-semibold uppercase mb-2">
                        <ThumbsUp className="w-3 h-3" />
                        Recommended
                      </span>
                    )}
                    <h5 className="font-medium text-sm text-gunmetal mb-1">
                      {control.name}
                    </h5>
                    <p className="text-xs text-gray-500 mb-3">
                      {control.why_it_exists}
                    </p>

                    {/* Approve/Reject buttons */}
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleApprove(control)}
                        disabled={isLoading}
                        className="h-8 bg-lime hover:bg-lime/90 text-gunmetal text-xs"
                      >
                        {isLoading ? (
                          <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5 mr-1.5" />
                        )}
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleReject(control)}
                        disabled={isLoading}
                        className="h-8 border-gray-200 text-xs"
                      >
                        {isLoading ? (
                          <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        ) : (
                          <X className="w-3.5 h-3.5 mr-1.5" />
                        )}
                        Reject
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => onControlClick(control)}
                        className="h-8 text-xs text-gray-500 ml-auto"
                      >
                        View Details
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Add custom action button */}
            <Button
              variant="outline"
              onClick={onAddCustomAction || onReviewWithTammy}
              className="w-full mt-3 h-9 border-dashed border-gray-300 text-gray-500 hover:text-gunmetal hover:border-gray-400"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add custom action
            </Button>
          </div>
        )}

        {/* Active Controls (already approved) */}
        {activeControls.length > 0 && (
          <div className="py-4 border-b border-gray-100">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              <Shield className="w-3.5 h-3.5" />
              Active Actions ({activeControls.length})
            </h4>
            <div className="space-y-2">
              {activeControls.map((control) => {
                const stateStyles = getControlStateStyles(control.state);
                return (
                  <button
                    key={control.id}
                    onClick={() => onControlClick(control)}
                    className="w-full flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors text-left"
                  >
                    <div
                      className={cn(
                        'w-2 h-2 rounded-full flex-shrink-0',
                        stateStyles.dotClass
                      )}
                    />
                    <Shield className={cn('w-4 h-4', stateStyles.textClass)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gunmetal truncate">
                        {control.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {control.state_label}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* No controls yet - show add action */}
        {linkedControls.length === 0 && (
          <div className="py-4 border-b border-gray-100">
            <div className="text-center py-4">
              <Shield className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500 mb-3">
                No actions prepared yet for this risk
              </p>
              <Button
                variant="outline"
                onClick={onAddCustomAction || onReviewWithTammy}
                className="border-dashed border-gray-300"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create an action
              </Button>
            </div>
          </div>
        )}

        {/* Prevention Tips (Collapsible) */}
        <Collapsible
          open={isPreventionOpen}
          onOpenChange={setIsPreventionOpen}
          className="py-4 border-b border-gray-100"
        >
          <CollapsibleTrigger className="flex items-center justify-between w-full group">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide flex items-center gap-2">
              <Lightbulb className="w-3.5 h-3.5" />
              Prevention Tips
            </h4>
            {isPreventionOpen ? (
              <ChevronUp className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
            )}
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-3 space-y-2 text-sm text-gray-600">
              <p className="flex items-start gap-2">
                <span className="text-lime-600 mt-0.5">•</span>
                <span>Set up automated payment reminders before due dates</span>
              </p>
              <p className="flex items-start gap-2">
                <span className="text-lime-600 mt-0.5">•</span>
                <span>Consider requiring deposits for large projects or new clients</span>
              </p>
              <p className="flex items-start gap-2">
                <span className="text-lime-600 mt-0.5">•</span>
                <span>Review client payment history before extending terms</span>
              </p>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Rejected Suggestions (Collapsible for Auditability) */}
        {rejectedSuggestions.length > 0 && (
          <Collapsible
            open={isRejectedOpen}
            onOpenChange={setIsRejectedOpen}
            className="py-4 border-b border-gray-100"
          >
            <CollapsibleTrigger className="flex items-center justify-between w-full group">
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide flex items-center gap-2">
                <ThumbsDown className="w-3.5 h-3.5" />
                Rejected Suggestions ({rejectedSuggestions.length})
              </h4>
              {isRejectedOpen ? (
                <ChevronUp className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-3 space-y-2">
                {rejectedSuggestions.map((suggestion) => (
                  <div
                    key={suggestion.id}
                    className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg opacity-60"
                  >
                    <X className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-600">{suggestion.title}</p>
                      {suggestion.reason && (
                        <p className="text-xs text-gray-400 mt-1">
                          Reason: {suggestion.reason}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Footer Actions */}
        <div className="pt-4 flex gap-3">
          <Button
            onClick={onReviewWithTammy}
            className="flex-1 bg-lime hover:bg-lime/90 text-gunmetal"
          >
            <MessageSquare className="w-4 h-4 mr-2" />
            Review with Tammy
          </Button>
          <Button
            variant="outline"
            onClick={onDismiss}
            className="border-gray-200"
          >
            <Check className="w-4 h-4 mr-2" />
            Dismiss
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
