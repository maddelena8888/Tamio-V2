/**
 * ControlDetailModal Component - V4 Risk/Controls Architecture
 *
 * Full detail view for a control, including:
 * - Control name and state
 * - Why it exists (linked to risk)
 * - Two-column responsibility split: Tamio handles | You handle
 * - Action steps with completion status
 * - State transition buttons
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
  Shield,
  Clock,
  DollarSign,
  AlertCircle,
  Check,
  Bot,
  User,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import type { Control, Risk } from '@/lib/api/alertsActions';
import {
  getControlStateStyles,
  updateControlState,
  completeControl,
  type ControlState,
} from '@/lib/api/alertsActions';
import { toast } from 'sonner';

interface ControlDetailModalProps {
  control: Control | null;
  linkedRisks: Risk[];
  onClose: () => void;
  onRiskClick: (risk: Risk) => void;
  onControlUpdated: () => void;
}

export function ControlDetailModal({
  control,
  linkedRisks,
  onClose,
  onRiskClick,
  onControlUpdated,
}: ControlDetailModalProps) {
  const [isUpdating, setIsUpdating] = useState(false);

  if (!control) return null;

  const stateStyles = getControlStateStyles(control.state);

  const formatAmount = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '--';
    const absValue = Math.abs(value);
    return `$${absValue.toLocaleString()}`;
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const handleStateChange = async (newState: ControlState) => {
    setIsUpdating(true);
    try {
      await updateControlState(control.id, { state: newState });
      toast.success(`Control moved to ${newState}`);
      onControlUpdated();
    } catch (error) {
      toast.error('Failed to update control state');
      console.error(error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleComplete = async () => {
    setIsUpdating(true);
    try {
      await completeControl(control.id);
      toast.success('Control marked as completed');
      onControlUpdated();
    } catch (error) {
      toast.error('Failed to complete control');
      console.error(error);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <Dialog open={!!control} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto bg-white">
        <DialogHeader className="pb-4 border-b border-gray-200">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center',
                  stateStyles.bgClass
                )}
              >
                <Shield className={cn('w-5 h-5', stateStyles.textClass)} />
              </div>
              <div>
                <DialogTitle className="text-base font-semibold text-gunmetal">
                  {control.name}
                </DialogTitle>
                <p className="text-xs text-gray-500 mt-1">
                  Created {formatDate(control.created_at)}
                </p>
              </div>
            </div>
            <span
              className={cn(
                'px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1.5',
                stateStyles.bgClass,
                stateStyles.textClass
              )}
            >
              <span className={cn('w-2 h-2 rounded-full', stateStyles.dotClass)} />
              {control.state_label}
            </span>
          </div>
        </DialogHeader>

        {/* Why Section */}
        <div className="py-4 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Why this control exists
          </h4>
          <p className="text-sm text-gray-600">{control.why_it_exists}</p>

          {/* Linked Risks */}
          {linkedRisks.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-2">Protects against:</p>
              <div className="space-y-2">
                {linkedRisks.map((risk) => (
                  <button
                    key={risk.id}
                    onClick={() => onRiskClick(risk)}
                    className="w-full flex items-center gap-2 p-2 bg-tomato/5 rounded-lg hover:bg-tomato/10 transition-colors text-left"
                  >
                    <AlertCircle className="w-4 h-4 text-tomato flex-shrink-0" />
                    <span className="text-sm text-gunmetal truncate">
                      {risk.title}
                    </span>
                    <ArrowRight className="w-3 h-3 text-gray-400 ml-auto" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Impact & Timeline */}
        <div className="py-4 border-b border-gray-100">
          <div className="grid grid-cols-2 gap-4">
            {control.impact_amount && (
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <DollarSign className="w-4 h-4 text-gray-400" />
                  <span className="text-xs text-gray-500">Impact</span>
                </div>
                <p className="text-lg font-bold text-gunmetal">
                  {formatAmount(control.impact_amount)}
                </p>
              </div>
            )}

            {control.deadline && (
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Clock className="w-4 h-4 text-gray-400" />
                  <span className="text-xs text-gray-500">Deadline</span>
                </div>
                <p className="text-sm font-semibold text-gunmetal">
                  {formatDate(control.deadline)}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Responsibility Split */}
        <div className="py-4 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Responsibility Split
          </h4>
          <div className="grid grid-cols-2 gap-4">
            {/* Tamio Handles */}
            <div className="bg-lime/5 rounded-lg p-3 border border-lime/20">
              <div className="flex items-center gap-2 mb-3">
                <Bot className="w-4 h-4 text-lime-600" />
                <span className="text-xs font-semibold text-lime-700">
                  Tamio handles
                </span>
              </div>
              <ul className="space-y-2">
                {control.tamio_handles.map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-xs text-gray-600"
                  >
                    <Check className="w-3 h-3 text-lime-600 flex-shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* User Handles */}
            <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
              <div className="flex items-center gap-2 mb-3">
                <User className="w-4 h-4 text-blue-600" />
                <span className="text-xs font-semibold text-blue-700">
                  You handle
                </span>
              </div>
              <ul className="space-y-2">
                {control.user_handles.map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 text-xs text-gray-600"
                  >
                    <span className="w-3 h-3 rounded-full border border-blue-300 flex-shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Action Steps */}
        {control.action_steps.length > 0 && (
          <div className="py-4 border-b border-gray-100">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Steps
            </h4>
            <div className="space-y-2">
              {control.action_steps.map((step) => (
                <div
                  key={step.id}
                  className={cn(
                    'flex items-center gap-3 p-3 rounded-lg',
                    step.status === 'completed'
                      ? 'bg-green-50'
                      : step.status === 'in_progress'
                      ? 'bg-blue-50'
                      : 'bg-gray-50'
                  )}
                >
                  {step.status === 'completed' ? (
                    <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                      <Check className="w-3 h-3 text-white" />
                    </div>
                  ) : step.status === 'in_progress' ? (
                    <div className="w-5 h-5 rounded-full border-2 border-blue-500 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-blue-500" />
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
                  )}
                  <div className="flex-1">
                    <p className="text-sm text-gunmetal">{step.title}</p>
                  </div>
                  <span
                    className={cn(
                      'text-xs px-2 py-0.5 rounded-full',
                      step.owner === 'tamio'
                        ? 'bg-lime/10 text-lime-700'
                        : 'bg-blue-100 text-blue-700'
                    )}
                  >
                    {step.owner === 'tamio' ? 'Tamio' : 'You'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* State Transition Actions */}
        <div className="pt-4">
          <div className="flex gap-3">
            {control.state === 'active' && (
              <Button
                onClick={handleComplete}
                disabled={isUpdating}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white"
              >
                {isUpdating ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Check className="w-4 h-4 mr-2" />
                )}
                Mark Complete
              </Button>
            )}

            {control.state === 'pending' && (
              <Button
                onClick={() => handleStateChange('active')}
                disabled={isUpdating}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
              >
                {isUpdating ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <ArrowRight className="w-4 h-4 mr-2" />
                )}
                Start Progress
              </Button>
            )}

            {control.state === 'completed' && (
              <Button
                onClick={() => handleStateChange('active')}
                disabled={isUpdating}
                variant="outline"
                className="flex-1"
              >
                {isUpdating ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : null}
                Reopen
              </Button>
            )}

            {control.state === 'needs_review' && (
              <>
                <Button
                  onClick={() => handleStateChange('active')}
                  disabled={isUpdating}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                >
                  Resume
                </Button>
                <Button
                  onClick={() => handleStateChange('pending')}
                  disabled={isUpdating}
                  variant="outline"
                >
                  Reset
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
