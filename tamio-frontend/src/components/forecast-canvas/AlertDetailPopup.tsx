/**
 * AlertDetailPopup Component
 *
 * Popup dialog for alert details shown when clicking alerts on the canvas page.
 * Mirrors the DecisionCard structure from the alerts page with:
 * - Title and severity badge
 * - Impact statement
 * - Context/insight text
 * - View Impact button
 * - Recommended Actions section
 * - Chat input bar for TAMI (instead of Chat with TAMI button)
 */

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import {
  X,
  AlertCircle,
  Calendar,
  Clock,
  Mail,
  Phone,
  FileText,
  ArrowDownRight,
  AlertTriangle,
  User,
  Receipt,
  Users,
  Building2,
  DollarSign,
  BarChart2,
  ExternalLink,
  Send,
  Loader2,
  Bot,
  Plus,
  Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTAMI } from '@/contexts/TAMIContext';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';

// ============================================================================
// Types
// ============================================================================

export interface CanvasAlert {
  id: string;
  tier: 'act-now' | 'monitor';
  type: string;
  title: string;
  subtitle: string;
  body: string;
  primaryAction?: string;
  secondaryAction?: string;
  severity?: 'urgent' | 'high' | 'normal';
  impact?: string;
  dueDate?: string;
  linkedEntity?: {
    type: 'client' | 'expense' | 'payroll' | 'tax' | 'vendor';
    name: string;
  };
  recommendedActions?: Array<{
    icon: 'email' | 'phone' | 'invoice' | 'transfer' | 'schedule' | 'review';
    label: string;
    description?: string;
    primary?: boolean;
  }>;
}

interface AlertDetailPopupProps {
  alert: CanvasAlert;
  isOpen: boolean;
  onClose: () => void;
}

// ============================================================================
// Utility Functions & Components
// ============================================================================

const getSeverityFromTier = (tier: 'act-now' | 'monitor'): 'urgent' | 'high' | 'normal' => {
  return tier === 'act-now' ? 'urgent' : 'normal';
};

const severityStyles = {
  urgent: {
    bgClass: 'bg-tomato/10',
    textClass: 'text-tomato',
    borderClass: 'border-tomato/30',
  },
  high: {
    bgClass: 'bg-amber-500/10',
    textClass: 'text-amber-700',
    borderClass: 'border-amber-500/30',
  },
  normal: {
    bgClass: 'bg-lime/10',
    textClass: 'text-lime-700',
    borderClass: 'border-lime/30',
  },
};

const ActionIcon = ({ type }: { type: string }) => {
  switch (type) {
    case 'email':
      return <Mail className="w-4 h-4" />;
    case 'phone':
      return <Phone className="w-4 h-4" />;
    case 'invoice':
      return <FileText className="w-4 h-4" />;
    case 'transfer':
      return <ArrowDownRight className="w-4 h-4" />;
    case 'schedule':
      return <Calendar className="w-4 h-4" />;
    case 'review':
      return <AlertTriangle className="w-4 h-4" />;
    default:
      return <FileText className="w-4 h-4" />;
  }
};

const EntityIcon = ({ type }: { type: string | null }) => {
  switch (type) {
    case 'client':
      return <User className="w-3 h-3" />;
    case 'expense':
    case 'vendor':
      return <Receipt className="w-3 h-3" />;
    case 'payroll':
      return <Users className="w-3 h-3" />;
    case 'tax':
      return <Building2 className="w-3 h-3" />;
    default:
      return <DollarSign className="w-3 h-3" />;
  }
};

const getEntityColors = (type: string | null): string => {
  switch (type) {
    case 'client':
      return 'bg-blue-50 text-blue-700';
    case 'expense':
    case 'vendor':
      return 'bg-purple-50 text-purple-700';
    case 'payroll':
      return 'bg-emerald-50 text-emerald-700';
    case 'tax':
      return 'bg-amber-50 text-amber-700';
    default:
      return 'bg-gray-50 text-gray-700';
  }
};

// Generate default recommended actions based on alert tier and type
function getDefaultActions(alert: CanvasAlert) {
  if (alert.recommendedActions) {
    return alert.recommendedActions;
  }

  const actions: Array<{
    icon: 'email' | 'phone' | 'invoice' | 'transfer' | 'schedule' | 'review';
    label: string;
    description?: string;
    primary?: boolean;
  }> = [];

  if (alert.tier === 'act-now') {
    if (alert.type === 'overdue') {
      actions.push({
        icon: 'email',
        label: 'Send payment reminder',
        description: 'Follow up on overdue payment',
        primary: true,
      });
    } else {
      actions.push({
        icon: 'review',
        label: 'Review and take action',
        description: 'Assess the situation',
        primary: true,
      });
    }
  } else {
    actions.push({
      icon: 'schedule',
      label: 'Schedule payment',
      description: 'Set up payment before deadline',
      primary: true,
    });
  }

  return actions;
}

// ============================================================================
// Chat Input Component
// ============================================================================

function ChatInputBar({ alertTitle }: { alertTitle: string }) {
  const { sendMessage, isLoading, open: openTAMI } = useTAMI();
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const message = input.trim();
    setInput('');
    openTAMI();
    await sendMessage(`Regarding "${alertTitle}": ${message}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-200 pt-4 mt-4">
      <div className="flex items-center gap-2 mb-2">
        <Bot className="w-4 h-4 text-lime-600" />
        <span className="text-xs font-medium text-gray-600">Ask TAMI about this alert</span>
      </div>
      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What would you like to know?"
          disabled={isLoading}
          rows={1}
          className={cn(
            'flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2',
            'text-sm placeholder:text-gray-400',
            'focus:outline-none focus:ring-2 focus:ring-lime/50 focus:border-lime',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'max-h-20'
          )}
          style={{ minHeight: '40px' }}
        />
        <Button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="h-10 w-10 p-0 bg-lime hover:bg-lime/90 text-gunmetal rounded-xl flex-shrink-0"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Custom Action Section
// ============================================================================

function CustomActionSection() {
  const [showAddForm, setShowAddForm] = useState(false);
  const [customActionInput, setCustomActionInput] = useState('');
  const [customActions, setCustomActions] = useState<Array<{ id: string; label: string }>>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showAddForm && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showAddForm]);

  const handleAddCustomAction = () => {
    if (customActionInput.trim()) {
      setCustomActions([
        ...customActions,
        { id: `custom-${Date.now()}`, label: customActionInput.trim() },
      ]);
      setCustomActionInput('');
      setShowAddForm(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddCustomAction();
    } else if (e.key === 'Escape') {
      setShowAddForm(false);
      setCustomActionInput('');
    }
  };

  return (
    <>
      {/* Custom actions */}
      {customActions.map((action) => (
        <div
          key={action.id}
          className="flex items-center gap-3 p-2.5 rounded-lg bg-emerald-50/80 border border-emerald-100"
        >
          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-emerald-100 text-emerald-600">
            <Check className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-emerald-900">
              {action.label}
              <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-emerald-100 text-emerald-600 rounded uppercase font-semibold">
                Custom
              </span>
            </p>
          </div>
          <button
            onClick={() => setCustomActions(customActions.filter((a) => a.id !== action.id))}
            className="p-1 rounded text-emerald-400 hover:text-emerald-600 hover:bg-emerald-100 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}

      {/* Inline add form */}
      {showAddForm && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-gray-50 border border-gray-200">
          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 bg-gray-200 text-gray-500">
            <Plus className="w-4 h-4" />
          </div>
          <input
            ref={inputRef}
            type="text"
            value={customActionInput}
            onChange={(e) => setCustomActionInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your action..."
            className="flex-1 text-sm bg-transparent border-none outline-none placeholder:text-gray-400"
          />
          <button
            onClick={handleAddCustomAction}
            disabled={!customActionInput.trim()}
            className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Check className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setShowAddForm(false);
              setCustomActionInput('');
            }}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Add custom action button */}
      {!showAddForm && (
        <div className="pt-3 mt-3 border-t border-gray-200">
          <button
            onClick={() => setShowAddForm(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add custom action
          </button>
        </div>
      )}
    </>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function AlertDetailPopup({ alert, isOpen, onClose }: AlertDetailPopupProps) {
  const navigate = useNavigate();
  const severity = alert.severity || getSeverityFromTier(alert.tier);
  const styles = severityStyles[severity];
  const actions = getDefaultActions(alert);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-[100]"
        onClick={onClose}
      />

      {/* Popup */}
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 pointer-events-none">
        <NeuroCard
          className={cn(
            'w-full max-w-lg max-h-[85vh] overflow-y-auto pointer-events-auto',
            'bg-white border-gray-200 shadow-xl',
            'animate-in fade-in-0 zoom-in-95 duration-200'
          )}
        >
          <div className="p-6">
            {/* Header - Title with close button */}
            <div className="flex items-start justify-between gap-4 mb-3">
              <h2 className="text-xl font-bold text-gunmetal leading-snug">
                {alert.title}
              </h2>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Metadata badges row */}
            <div className="flex flex-wrap items-center gap-2 mb-5">
              {/* Linked entity pill */}
              {alert.linkedEntity && (
                <span
                  className={cn(
                    'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
                    getEntityColors(alert.linkedEntity.type)
                  )}
                >
                  <EntityIcon type={alert.linkedEntity.type} />
                  {alert.linkedEntity.name}
                </span>
              )}
              {/* Severity tag */}
              <span
                className={cn(
                  'px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wide',
                  styles.bgClass,
                  styles.textClass
                )}
              >
                {severity}
              </span>
              {/* Due date tag */}
              {alert.dueDate && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                  <Clock className="w-3 h-3" />
                  {alert.dueDate}
                </span>
              )}
            </div>

            {/* Subtitle */}
            <p className="text-sm text-gray-500 mb-3">{alert.subtitle}</p>

            {/* Impact statement */}
            {alert.impact && (
              <p className="text-sm font-medium text-tomato/90 mb-3">{alert.impact}</p>
            )}

            {/* Body / Insight */}
            <p className="text-sm text-gray-600 leading-relaxed mb-5">{alert.body}</p>

            {/* View Impact Button */}
            <div className="flex items-center gap-3 mb-5">
              <button
                onClick={() => navigate(`/alerts/${alert.id}/impact`)}
                className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-lg transition-colors bg-tomato text-white hover:bg-tomato/90 shadow-sm"
              >
                <BarChart2 className="w-4 h-4" />
                View Impact
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Recommended Actions Section */}
            {actions.length > 0 && (
              <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                <h4 className="text-sm font-semibold text-gunmetal mb-3">
                  Recommended Actions
                </h4>
                <div className="space-y-2">
                  {actions.map((action, index) => (
                    <div
                      key={index}
                      className={cn(
                        'flex items-center gap-3 p-3 rounded-lg',
                        action.primary
                          ? 'bg-blue-50 border border-blue-100'
                          : 'bg-white border border-gray-100'
                      )}
                    >
                      <div
                        className={cn(
                          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                          action.primary
                            ? 'bg-blue-100 text-blue-600'
                            : 'bg-gray-200 text-gray-500'
                        )}
                      >
                        <ActionIcon type={action.icon} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className={cn(
                            'text-sm font-medium',
                            action.primary ? 'text-blue-900' : 'text-gunmetal'
                          )}
                        >
                          {action.label}
                          {action.primary && (
                            <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded uppercase font-semibold">
                              Recommended
                            </span>
                          )}
                        </p>
                        {action.description && (
                          <p className="text-xs text-gray-500 truncate">
                            {action.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Custom Actions */}
                  <CustomActionSection />
                </div>
              </div>
            )}

            {/* Chat Input Bar */}
            <ChatInputBar alertTitle={alert.title} />
          </div>
        </NeuroCard>
      </div>
    </>,
    document.body
  );
}
