/**
 * ForecastCanvas - Canvas-First Design
 *
 * Full-page forecast canvas with:
 * - Floating glassomorphic toolbar (Figma-style)
 * - Compact KPIs as overlay
 * - TAMI chat bar
 * - Collapsible right sidebar for alerts/activity/rules
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Sparkles,
  Send,
  Mic,
  TrendingUp,
  TrendingDown,
  MessageSquare,
  Lightbulb,
  Layers,
  PanelRightClose,
  PanelLeft,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ChevronRight,
  Activity,
  GripVertical,
  ArrowDownRight,
  ArrowUpRight,
  Users,
  Download,
  Copy,
  ShieldCheck,
  ChevronDown,
  Upload,
  AtSign,
  X,
  Plus,
  Share2,
  CheckSquare,
  ArrowRightLeft,
  User,
  Wallet,
  Receipt,
  FileText,
  Gauge,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { useAuth } from '@/contexts/AuthContext';
import { useTAMI, useTAMIPageContext } from '@/contexts/TAMIContext';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import { getForecast } from '@/lib/api/forecast';
import { getCashPosition } from '@/lib/api/data';
import { getRules, getScenarioSuggestions, createScenario, buildScenario, getScenarioForecast } from '@/lib/api/scenarios';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { ManualScenarioModal, type ManualScenarioParams } from '@/components/forecast/ManualScenarioModal';
import { getRisks, getControls, type Risk, type Control } from '@/lib/api/alertsActions';
import { getAgentActivity, type AgentActivityStats } from '@/lib/api/actionMonitor';
import { NotificationsDropdown } from '@/components/notifications/NotificationsDropdown';
import { AlertDetailPopup, type CanvasAlert } from '@/components/forecast-canvas/AlertDetailPopup';
import type {
  ForecastResponse,
  ForecastWeek,
  CashPositionResponse,
  FinancialRule,
  ScenarioType,
} from '@/lib/api/types';

export type LayerToggle = 'confidence' | 'comments' | 'ai';
export type SidebarTab = 'alerts' | 'activity' | 'rules';
export type TimeRange = '13w' | '26w' | '52w';

// Trend data for week-over-week comparison
export interface TrendData {
  direction: 'up' | 'down' | 'flat';
  percent: number;
}

// Metrics data structure
export interface CanvasMetrics {
  cashPosition: number;
  income30d: number;
  expenses30d: number;
  runwayWeeks: number;
  cashSource?: string;
  lastUpdated?: string;
  trends?: {
    cashPosition?: TrendData;
    income?: TrendData;
    expenses?: TrendData;
    runway?: TrendData;
  };
}

// ============================================================================
// CompactKPI Component - Small glassomorphic KPI indicator
// ============================================================================

interface CompactKPIProps {
  label: string;
  value: string | number;
  trend?: 'up' | 'down';
  trendValue?: string;
}

function CompactKPI({ label, value, trend, trendValue }: CompactKPIProps) {
  return (
    <div className="glass-subtle rounded-xl px-4 py-2.5 flex items-center gap-3">
      <div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
          {label}
        </div>
        <div className="text-base font-semibold text-gunmetal">{value}</div>
      </div>
      {trend && (
        <div
          className={cn(
            'flex items-center gap-0.5 text-xs font-medium',
            trend === 'up' ? 'text-green-600' : 'text-red-500'
          )}
        >
          {trend === 'up' ? (
            <TrendingUp className="w-3 h-3" />
          ) : (
            <TrendingDown className="w-3 h-3" />
          )}
          {trendValue && <span>{trendValue}</span>}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// CanvasToolbar Component - Figma-style floating toolbar
// ============================================================================

interface SuggestedScenario {
  id: string;
  name: string;
  description: string;
  impact: string;
  impactDirection: 'positive' | 'negative' | 'neutral';
  type: 'revenue_gain' | 'expense' | 'delay' | 'revenue_loss';
  scenario_type?: string;
  prefill_params?: Record<string, unknown>;
}

interface CanvasToolbarProps {
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  showConfidence: boolean;
  onToggleConfidence: () => void;
  showComments: boolean;
  onToggleComments: () => void;
  showInsights: boolean;
  onToggleInsights: () => void;
  alertCount?: number;
  suggestedScenarios: SuggestedScenario[];
  onApplyScenario: (scenario: SuggestedScenario) => void;
  onBuildCustomScenario: () => void;
  isScenariosLoading?: boolean;
}

interface CanvasToolbarExtendedProps extends CanvasToolbarProps {
  sidebarOpen: boolean;
}

function CanvasToolbar({
  timeRange,
  onTimeRangeChange,
  showConfidence,
  onToggleConfidence,
  showComments,
  onToggleComments,
  showInsights,
  onToggleInsights,
  alertCount = 0,
  suggestedScenarios,
  onApplyScenario,
  onBuildCustomScenario,
  isScenariosLoading,
  sidebarOpen,
}: CanvasToolbarExtendedProps) {
  const [scenariosOpen, setScenariosOpen] = useState(false);

  return (
    <div className={cn(
      'absolute top-4 z-20 flex items-center gap-2 transition-all duration-300',
      sidebarOpen ? 'right-[340px]' : 'right-4'
    )}>
      {/* Legend */}
      <div className="bg-white/80 backdrop-blur-sm rounded-lg px-3 py-2 flex items-center gap-4 text-xs border border-gray-200/50 shadow-sm">
        <div className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 bg-gunmetal rounded" />
          <span className="text-muted-foreground">Forecast</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-4 h-0.5 border-t-2 border-dashed border-amber-500" />
          <span className="text-muted-foreground">Buffer</span>
        </div>
        {showConfidence && (
          <>
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 border-t-2 border-dashed border-green-500" />
              <span className="text-muted-foreground">Best</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-4 h-0.5 border-t-2 border-dashed border-red-500" />
              <span className="text-muted-foreground">Worst</span>
            </div>
          </>
        )}
      </div>

      {/* Time Range Selector */}
      <div className="bg-white/80 backdrop-blur-sm rounded-lg p-1 flex items-center gap-0.5 border border-gray-200/50 shadow-sm">
        {(['13w', '26w', '52w'] as TimeRange[]).map((range) => (
          <button
            key={range}
            onClick={() => onTimeRangeChange(range)}
            className={cn(
              'px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200',
              timeRange === range
                ? 'bg-gunmetal text-white shadow-sm'
                : 'text-gunmetal/60 hover:bg-gray-100'
            )}
          >
            {range}
          </button>
        ))}
      </div>

      {/* Layer Toggles */}
      <div className="bg-white/80 backdrop-blur-sm rounded-lg p-1 flex items-center gap-0.5 border border-gray-200/50 shadow-sm">
        <button
          onClick={onToggleConfidence}
          className={cn(
            'px-2.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 flex items-center gap-1.5',
            showConfidence
              ? 'bg-gunmetal text-white shadow-sm'
              : 'text-gunmetal/60 hover:bg-gray-100'
          )}
        >
          <Activity className="w-3.5 h-3.5" />
          <span className="hidden lg:inline">Confidence</span>
        </button>

        <button
          onClick={onToggleComments}
          className={cn(
            'px-2.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 flex items-center gap-1.5',
            showComments
              ? 'bg-gunmetal text-white shadow-sm'
              : 'text-gunmetal/60 hover:bg-gray-100'
          )}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span className="hidden lg:inline">Comments</span>
        </button>

        <button
          onClick={onToggleInsights}
          className={cn(
            'px-2.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 flex items-center gap-1.5 relative',
            showInsights
              ? 'bg-gunmetal text-white shadow-sm'
              : 'text-gunmetal/60 hover:bg-gray-100'
          )}
        >
          <Lightbulb className="w-3.5 h-3.5" />
          <span className="hidden lg:inline">Insights</span>
          {alertCount > 0 && !showInsights && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
              {alertCount > 9 ? '9+' : alertCount}
            </span>
          )}
        </button>

        {/* Scenarios Popover */}
        <Popover open={scenariosOpen} onOpenChange={setScenariosOpen}>
          <PopoverTrigger asChild>
            <button
              className={cn(
                'px-2.5 py-1.5 rounded-md text-xs font-medium transition-all duration-200 flex items-center gap-1.5',
                scenariosOpen
                  ? 'bg-gunmetal text-white shadow-sm'
                  : 'text-gunmetal/60 hover:bg-gray-100'
              )}
            >
              <Layers className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">Scenarios</span>
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            sideOffset={8}
            className="w-[340px] p-0 bg-white border border-gray-200 shadow-xl rounded-xl overflow-hidden"
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 px-4 py-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-purple-100 flex items-center justify-center">
                  <Layers className="w-4 h-4 text-purple-600" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-gunmetal">Scenarios</h3>
                  <p className="text-[10px] text-gray-500">Explore what-if impacts on your forecast</p>
                </div>
              </div>
            </div>

            {/* Scenarios List */}
            <div className="p-3 max-h-[380px] overflow-y-auto">
              <div className="space-y-2">
                {isScenariosLoading ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="p-3 rounded-xl bg-gray-50 animate-pulse">
                        <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                        <div className="h-3 bg-gray-100 rounded w-full mb-2" />
                        <div className="h-5 bg-gray-200 rounded w-1/3" />
                      </div>
                    ))}
                  </div>
                ) : suggestedScenarios.length > 0 ? (
                  suggestedScenarios.map((scenario) => (
                    <button
                      key={scenario.id}
                      onClick={() => {
                        onApplyScenario(scenario);
                        setScenariosOpen(false);
                      }}
                      className={cn(
                        'w-full text-left p-3 rounded-xl transition-all duration-200 group',
                        'bg-gray-50/80 hover:bg-white',
                        'border border-transparent hover:border-purple-200',
                        'hover:shadow-md hover:shadow-purple-100/50'
                      )}
                    >
                      {/* Scenario Name & Description */}
                      <div className="mb-2">
                        <span className="text-[13px] font-semibold text-gunmetal group-hover:text-purple-700 transition-colors leading-tight block">
                          {scenario.name}
                        </span>
                        <p className="text-[11px] text-gray-500 mt-0.5 leading-snug line-clamp-2">
                          {scenario.description}
                        </p>
                      </div>

                      {/* Impact Badge */}
                      <div className="flex items-center gap-1.5">
                        <span className={cn(
                          'inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-md',
                          scenario.impactDirection === 'positive'
                            ? 'bg-emerald-100 text-emerald-700'
                            : scenario.impactDirection === 'negative'
                            ? 'bg-red-50 text-red-600'
                            : 'bg-gray-100 text-gray-600'
                        )}>
                          {scenario.impactDirection === 'positive' ? (
                            <ArrowUpRight className="w-3 h-3" />
                          ) : scenario.impactDirection === 'negative' ? (
                            <ArrowDownRight className="w-3 h-3" />
                          ) : null}
                          {scenario.impact}
                        </span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="text-center py-6">
                    <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-2">
                      <Layers className="w-5 h-5 text-gray-400" />
                    </div>
                    <p className="text-xs text-gray-500">No scenarios available</p>
                    <p className="text-[10px] text-gray-400 mt-1">Create one below to get started</p>
                  </div>
                )}
              </div>
            </div>

            {/* Footer - Build Custom */}
            <div className="border-t border-gray-100 p-3 bg-gray-50/50">
              <button
                onClick={() => {
                  onBuildCustomScenario();
                  setScenariosOpen(false);
                }}
                className={cn(
                  'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg',
                  'bg-white border border-gray-200 hover:border-purple-300',
                  'text-sm font-medium text-gunmetal hover:text-purple-700',
                  'transition-all duration-200 hover:shadow-sm'
                )}
              >
                <Plus className="w-4 h-4" />
                Build custom scenario
              </button>
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}

// ============================================================================
// TAMIChatBar Component - Floating AI input bar
// ============================================================================

interface TAMIChatBarProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  onCommentDrag?: (isDragging: boolean) => void;
}

function TAMIChatBar({ onSend, isLoading, onCommentDrag }: TAMIChatBarProps) {
  const [value, setValue] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [isCommentDragging, setIsCommentDragging] = useState(false);

  const handleSubmit = () => {
    if (!value.trim() || isLoading) return;
    onSend(value);
    setValue('');
  };

  const handleVoiceClick = () => {
    toast.info('Voice input coming soon');
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    try {
      const jsonData = e.dataTransfer.getData('application/json');
      if (jsonData) {
        const weekData = JSON.parse(jsonData);
        const formatCurrency = (value: number) => {
          if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
          if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
          return `$${value.toFixed(0)}`;
        };

        // Pre-fill a contextual question about this week
        const question = `Tell me about Week ${weekData.weekNumber} (${weekData.weekStart} - ${weekData.weekEnd}). Balance: ${formatCurrency(weekData.balance)}, Income: ${formatCurrency(weekData.income)}, Costs: ${formatCurrency(weekData.costs)}. What should I know?`;
        setValue(question);

        // Focus the input
        const aiInput = document.querySelector<HTMLInputElement>('[data-ai-input]');
        aiInput?.focus();
      }
    } catch (err) {
      console.error('Failed to parse dropped data:', err);
    }
  };

  // Comment drag handlers
  const handleCommentDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData('application/comment-tool', 'true');
    e.dataTransfer.effectAllowed = 'copy';
    setIsCommentDragging(true);
    onCommentDrag?.(true);
  };

  const handleCommentDragEnd = () => {
    setIsCommentDragging(false);
    onCommentDrag?.(false);
  };

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-30 w-full max-w-2xl px-4">
      <div
        className={cn(
          'glass-strong rounded-2xl p-1.5 shadow-lg transition-all duration-200',
          isDragOver && 'ring-2 ring-lime ring-offset-2 scale-[1.02]'
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className={cn(
          'flex items-center gap-2 rounded-xl px-2 transition-colors',
          isDragOver ? 'bg-lime/20' : 'bg-white/60'
        )}>
          {/* Comment Tool - Draggable */}
          <div
            draggable
            onDragStart={handleCommentDragStart}
            onDragEnd={handleCommentDragEnd}
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 cursor-grab active:cursor-grabbing transition-all border',
              isCommentDragging
                ? 'bg-blue-500 text-white border-blue-600 scale-95'
                : 'bg-white/50 border-white/30 text-muted-foreground hover:bg-blue-500 hover:text-white hover:border-blue-600'
            )}
            title="Drag to add comment"
          >
            <MessageSquare className="w-4 h-4" />
          </div>

          {/* AI Icon */}
          <div className="w-8 h-8 bg-gunmetal rounded-lg flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4 text-lime" />
          </div>

          {/* Input */}
          <input
            type="text"
            data-ai-input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder='Ask anything... "Can I afford a hire?" "What if Acme pays late?"'
            className="flex-1 bg-transparent border-none text-gunmetal text-sm px-2 py-3 outline-none placeholder:text-muted-foreground"
            disabled={isLoading}
          />

          {/* Voice Button */}
          <button
            onClick={handleVoiceClick}
            className="w-8 h-8 rounded-lg bg-white/50 border border-white/30 text-muted-foreground flex items-center justify-center transition-all hover:bg-gunmetal hover:text-white hover:border-gunmetal"
            title="Voice input"
          >
            <Mic className="w-4 h-4" />
          </button>

          {/* Send Button */}
          <Button
            onClick={handleSubmit}
            disabled={!value.trim() || isLoading}
            size="sm"
            className="w-8 h-8 rounded-lg bg-gunmetal hover:bg-gunmetal/90 disabled:opacity-50"
            title="Send"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Chart Comment Types and Data
// ============================================================================

interface ChartComment {
  id: string;
  weekNumber: number;
  author: {
    name: string;
    initials: string;
    color: string;
    avatar?: string;
  };
  text: string;
  timestamp: string;
  resolved?: boolean;
}

// Team members for @ mentions
const teamMembers = [
  { id: '1', name: 'Jordan Davis', initials: 'JD', color: 'bg-green-500', email: 'jordan@company.com', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' },
  { id: '2', name: 'Alex Kim', initials: 'AK', color: 'bg-amber-500', email: 'alex@company.com', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face' },
  { id: '3', name: 'Taylor Smith', initials: 'TS', color: 'bg-purple-500', email: 'taylor@company.com', avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=face' },
  { id: '4', name: 'Morgan Lee', initials: 'ML', color: 'bg-blue-500', email: 'morgan@company.com', avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=face' },
  { id: '5', name: 'Casey Chen', initials: 'CC', color: 'bg-pink-500', email: 'casey@company.com', avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=face' },
];

// Mock comments positioned on specific weeks
const chartComments: ChartComment[] = [
  {
    id: '1',
    weekNumber: 3,
    author: { name: 'Jordan Davis', initials: 'JD', color: 'bg-green-500', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' },
    text: 'RetailCo payment expected here - should see a significant jump',
    timestamp: '2h ago',
  },
  {
    id: '2',
    weekNumber: 5,
    author: { name: 'Alex Kim', initials: 'AK', color: 'bg-amber-500', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face' },
    text: 'AWS bill increases start this week. Need to review our infrastructure costs.',
    timestamp: 'Yesterday',
  },
  {
    id: '3',
    weekNumber: 8,
    author: { name: 'Taylor Smith', initials: 'TS', color: 'bg-purple-500', avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=face' },
    text: 'Seasonal slowdown typically begins here. Q4 revenue usually dips ~15%.',
    timestamp: '3d ago',
  },
  {
    id: '4',
    weekNumber: 11,
    author: { name: 'Jordan Davis', initials: 'JD', color: 'bg-green-500', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' },
    text: 'New client onboarding should complete by this point',
    timestamp: '1w ago',
  },
];

// ============================================================================
// Chart Insight Types and Data (TAMI AI Insights)
// ============================================================================

interface ChartInsight {
  id: string;
  weekNumber: number;
  type: 'positive' | 'warning' | 'opportunity' | 'info';
  title: string;
  description: string;
  confidence: number;
}

// TAMI-generated insights positioned at relevant weeks
const chartInsights: ChartInsight[] = [
  {
    id: 'insight-1',
    weekNumber: 1,
    type: 'positive',
    title: 'Strong cash position',
    description: 'Your current runway exceeds the recommended 12-week buffer. This gives you flexibility for strategic investments.',
    confidence: 92,
  },
  {
    id: 'insight-2',
    weekNumber: 4,
    type: 'warning',
    title: 'Revenue concentration risk',
    description: 'Top 2 clients account for 65% of income. If RetailCo delays payment, runway drops to 8 weeks.',
    confidence: 87,
  },
  {
    id: 'insight-3',
    weekNumber: 7,
    type: 'opportunity',
    title: 'Expense optimization',
    description: 'Software subscriptions grew 23% YoY. Consolidating tools could save ~$2,400/month.',
    confidence: 78,
  },
  {
    id: 'insight-4',
    weekNumber: 10,
    type: 'info',
    title: 'Seasonal pattern detected',
    description: 'Historical data shows Q1 revenue typically dips 15%. Consider building reserves before Week 12.',
    confidence: 84,
  },
];

// ============================================================================
// InsightPin Component - TAMI AI insight marker
// ============================================================================

interface InsightPinProps {
  insight: ChartInsight;
  style: React.CSSProperties;
  positionAbove?: boolean;
}

function InsightPin({ insight, style, positionAbove = false }: InsightPinProps) {
  const [isHovered, setIsHovered] = useState(false);

  const typeBgColors = {
    positive: 'bg-lime/10 border-lime/30',
    warning: 'bg-amber-50 border-amber-200',
    opportunity: 'bg-purple-50 border-purple-200',
    info: 'bg-blue-50 border-blue-200',
  };

  const typeTextColors = {
    positive: 'text-lime-700',
    warning: 'text-amber-700',
    opportunity: 'text-purple-700',
    info: 'text-blue-700',
  };

  return (
    <div
      className={cn("absolute cursor-pointer group", isHovered ? "z-50" : "z-20")}
      style={style}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* TAMI Pin marker - sparkle style matching chatbot */}
      <div
        className={cn(
          'w-7 h-7 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 border-2 border-white bg-gunmetal',
          isHovered ? 'scale-110 ring-2 ring-lime ring-offset-2' : 'hover:scale-105'
        )}
      >
        <Sparkles className="w-3.5 h-3.5 text-lime" />
      </div>

      {/* Insight popover */}
      {isHovered && (
        <div className={cn(
          "absolute left-1/2 -translate-x-1/2 w-72 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden z-50",
          positionAbove ? "bottom-full mb-2" : "top-full mt-2"
        )}>
          {/* Arrow */}
          <div className={cn(
            "absolute left-1/2 -translate-x-1/2 w-4 h-4 bg-white transform",
            positionAbove
              ? "-bottom-2 border-r border-b border-gray-200 rotate-45"
              : "-top-2 border-l border-t border-gray-200 rotate-45"
          )} />

          {/* TAMI Header */}
          <div className="bg-gradient-to-r from-gunmetal to-gunmetal/90 px-3 py-2 flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-lime/20 flex items-center justify-center">
              <Sparkles className="w-3 h-3 text-lime" />
            </div>
            <span className="text-xs font-semibold text-white">TAMI Insight</span>
            <span className="ml-auto text-[10px] text-white/60">{insight.confidence}% confidence</span>
          </div>

          {/* Content */}
          <div className={cn('p-3 border-l-4', typeBgColors[insight.type])}>
            <h4 className={cn('text-sm font-semibold mb-1', typeTextColors[insight.type])}>
              {insight.title}
            </h4>
            <p className="text-xs text-gray-600 leading-relaxed">{insight.description}</p>
          </div>

          {/* Actions */}
          <div className="px-3 py-2 border-t border-gray-100 flex items-center justify-between bg-gray-50/50">
            <button className="text-[10px] text-gray-500 hover:text-gunmetal transition-colors">Dismiss</button>
            <button className="text-[10px] font-medium text-lime-700 hover:text-lime-800 transition-colors flex items-center gap-1">
              Ask TAMI more
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Custom Alert Triangle Icon - Filled triangle with exclamation mark
// ============================================================================

function AlertTriangleIcon({ className, fill = 'currentColor' }: { className?: string; fill?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill={fill}
    >
      <path
        d="M12 2L1 21h22L12 2z"
        fill={fill}
        stroke="none"
      />
      <rect x="11" y="9" width="2" height="6" rx="1" fill="white" />
      <circle cx="12" cy="17" r="1" fill="white" />
    </svg>
  );
}

// ============================================================================
// AlertPin Component - Urgent alert marker with link to alert details
// ============================================================================

interface AlertPinProps {
  alert: Risk;
  style: React.CSSProperties;
  positionAbove?: boolean;
  onClick?: (alert: Risk) => void;
}

function AlertPin({ alert, style, positionAbove = false, onClick }: AlertPinProps) {
  const [isHovered, setIsHovered] = useState(false);

  const severityFillColors = {
    urgent: '#ef4444', // red-500
    high: '#f59e0b',   // amber-500
    normal: '#3b82f6', // blue-500
  };

  const severityBgColors = {
    urgent: 'bg-red-50 border-red-200',
    high: 'bg-amber-50 border-amber-200',
    normal: 'bg-blue-50 border-blue-200',
  };

  const severityTextColors = {
    urgent: 'text-red-700',
    high: 'text-amber-700',
    normal: 'text-blue-700',
  };

  return (
    <div
      className={cn("absolute cursor-pointer group", isHovered ? "z-50" : "z-20")}
      style={style}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onClick?.(alert)}
    >
      {/* Alert Pin marker - filled triangle */}
      <div
        className={cn(
          'w-8 h-8 flex items-center justify-center transition-all duration-200 drop-shadow-lg',
          isHovered ? 'scale-110' : 'hover:scale-105'
        )}
      >
        <AlertTriangleIcon className="w-8 h-8" fill={severityFillColors[alert.severity]} />
      </div>

      {/* Alert popover */}
      {isHovered && (
        <div className={cn(
          "absolute left-1/2 -translate-x-1/2 w-72 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden z-50",
          positionAbove ? "bottom-full mb-2" : "top-full mt-2"
        )}>
          {/* Arrow */}
          <div className={cn(
            "absolute left-1/2 -translate-x-1/2 w-4 h-4 bg-white transform",
            positionAbove
              ? "-bottom-2 border-r border-b border-gray-200 rotate-45"
              : "-top-2 border-l border-t border-gray-200 rotate-45"
          )} />

          {/* Header */}
          <div className={cn('px-3 py-2 flex items-center gap-2', severityBgColors[alert.severity])}>
            <AlertTriangleIcon className="w-5 h-5" fill={severityFillColors[alert.severity]} />
            <span className={cn('text-xs font-semibold', severityTextColors[alert.severity])}>
              {alert.severity === 'urgent' ? 'Urgent Alert' : alert.severity === 'high' ? 'High Priority' : 'Alert'}
            </span>
            <span className="ml-auto text-[10px] text-gray-500">{alert.due_horizon_label}</span>
          </div>

          {/* Content */}
          <div className="p-3">
            <h4 className="text-sm font-semibold text-gunmetal mb-1">{alert.title}</h4>
            <p className="text-xs text-gray-600 leading-relaxed">{alert.primary_driver}</p>
            {alert.cash_impact && (
              <p className="text-xs font-medium text-red-600 mt-2">
                Impact: ${Math.abs(alert.cash_impact).toLocaleString()}
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="px-3 py-2 border-t border-gray-100 flex items-center justify-between bg-gray-50/50">
            <span className="text-[10px] text-gray-500">Click to view details</span>
            <button className="text-[10px] font-medium text-red-600 hover:text-red-700 transition-colors flex items-center gap-1">
              View Alert
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// CommentPin Component - Figma-style comment marker
// ============================================================================

interface CommentPinProps {
  comment: ChartComment;
  style: React.CSSProperties;
  positionAbove?: boolean;
}

function CommentPin({ comment, style, positionAbove = false }: CommentPinProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={cn("absolute cursor-pointer group", isHovered ? "z-50" : "z-20")}
      style={style}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Pin marker */}
      <div
        className={cn(
          'w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold shadow-lg transition-all duration-200 overflow-hidden',
          comment.author.color,
          isHovered ? 'scale-110 ring-2 ring-white ring-offset-2' : 'hover:scale-105'
        )}
      >
        {comment.author.avatar ? (
          <img src={comment.author.avatar} alt={comment.author.name} className="w-full h-full object-cover" />
        ) : (
          comment.author.initials
        )}
      </div>

      {/* Comment popover */}
      {isHovered && (
        <div className={cn(
          "absolute left-1/2 -translate-x-1/2 w-64 bg-white rounded-xl shadow-2xl border border-gray-200 p-3 z-50",
          positionAbove ? "bottom-full mb-2" : "top-full mt-2"
        )}>
          {/* Arrow */}
          <div className={cn(
            "absolute left-1/2 -translate-x-1/2 w-4 h-4 bg-white transform",
            positionAbove
              ? "-bottom-2 border-r border-b border-gray-200 rotate-45"
              : "-top-2 border-l border-t border-gray-200 rotate-45"
          )} />

          {/* Header */}
          <div className="flex items-center gap-2 mb-2 relative">
            <div className={cn('w-6 h-6 rounded-full flex items-center justify-center text-white text-[9px] font-bold overflow-hidden', comment.author.color)}>
              {comment.author.avatar ? (
                <img src={comment.author.avatar} alt={comment.author.name} className="w-full h-full object-cover" />
              ) : (
                comment.author.initials
              )}
            </div>
            <div className="flex-1">
              <p className="text-xs font-semibold text-gunmetal">{comment.author.name}</p>
              <p className="text-[10px] text-gray-400">{comment.timestamp}</p>
            </div>
          </div>

          {/* Comment text */}
          <p className="text-sm text-gray-700 leading-relaxed">{comment.text}</p>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-3 pt-2 border-t border-gray-100">
            <button className="text-[10px] text-gray-500 hover:text-gunmetal transition-colors">Reply</button>
            <span className="text-gray-300">·</span>
            <button className="text-[10px] text-gray-500 hover:text-gunmetal transition-colors">Resolve</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// AddCommentPopup Component - Figma-style comment creation
// ============================================================================

interface NewCommentPosition {
  x: number;
  y: number;
  weekNumber: number;
}

interface AddCommentPopupProps {
  position: NewCommentPosition;
  onSubmit: (comment: { text: string; mentions: string[]; weekNumber: number }) => void;
  onClose: () => void;
}

function AddCommentPopup({ position, onSubmit, onClose }: AddCommentPopupProps) {
  const [text, setText] = useState('');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [selectedMentions, setSelectedMentions] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Filter team members based on search
  const filteredMembers = teamMembers.filter(member =>
    member.name.toLowerCase().includes(mentionFilter.toLowerCase())
  );

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    setText(newText);

    // Check for @ trigger
    const lastAtIndex = newText.lastIndexOf('@');
    if (lastAtIndex !== -1) {
      const textAfterAt = newText.slice(lastAtIndex + 1);
      // Show mentions if @ is at end or followed by non-space characters
      if (textAfterAt === '' || !textAfterAt.includes(' ')) {
        setShowMentions(true);
        setMentionFilter(textAfterAt);
      } else {
        setShowMentions(false);
      }
    } else {
      setShowMentions(false);
    }
  };

  const handleMentionSelect = (member: typeof teamMembers[0]) => {
    // Replace the @filter with @name
    const lastAtIndex = text.lastIndexOf('@');
    const newText = text.slice(0, lastAtIndex) + `@${member.name} `;
    setText(newText);
    setShowMentions(false);
    setMentionFilter('');
    if (!selectedMentions.includes(member.id)) {
      setSelectedMentions([...selectedMentions, member.id]);
    }
    textareaRef.current?.focus();
  };

  const handleSubmit = () => {
    if (!text.trim()) return;
    onSubmit({
      text: text.trim(),
      mentions: selectedMentions,
      weekNumber: position.weekNumber,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      className="absolute z-50"
      style={{
        left: position.x,
        top: position.y,
        transform: 'translate(-50%, 8px)',
      }}
    >
      {/* Arrow pointing up */}
      <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-white border-l border-t border-gray-200 transform rotate-45 z-10" />

      <div className="bg-white rounded-xl shadow-2xl border border-gray-200 w-80 overflow-hidden">
        {/* Header */}
        <div className="px-3 py-2 border-b border-gray-100 flex items-center justify-between bg-gray-50/50">
          <div className="flex items-center gap-2">
            <Plus className="w-4 h-4 text-gunmetal" />
            <span className="text-xs font-semibold text-gunmetal">Add Comment</span>
            <span className="text-[10px] text-muted-foreground">Week {position.weekNumber}</span>
          </div>
          <button
            onClick={onClose}
            className="w-6 h-6 rounded-md hover:bg-gray-200 flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Text input */}
        <div className="p-3 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={handleTextChange}
            onKeyDown={handleKeyDown}
            placeholder="Add a comment... Use @ to mention someone"
            className="w-full h-20 text-sm text-gunmetal bg-transparent border-none outline-none resize-none placeholder:text-muted-foreground"
          />

          {/* Mention suggestions dropdown */}
          {showMentions && filteredMembers.length > 0 && (
            <div className="absolute left-3 right-3 top-full bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden z-20">
              {filteredMembers.map((member) => (
                <button
                  key={member.id}
                  onClick={() => handleMentionSelect(member)}
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className={cn('w-6 h-6 rounded-full flex items-center justify-center text-white text-[9px] font-bold overflow-hidden', member.color)}>
                    {member.avatar ? (
                      <img src={member.avatar} alt={member.name} className="w-full h-full object-cover" />
                    ) : (
                      member.initials
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gunmetal">{member.name}</div>
                    <div className="text-[10px] text-muted-foreground">{member.email}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected mentions */}
        {selectedMentions.length > 0 && (
          <div className="px-3 pb-2 flex flex-wrap gap-1">
            {selectedMentions.map((id) => {
              const member = teamMembers.find(m => m.id === id);
              if (!member) return null;
              return (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-[10px] font-medium"
                >
                  @{member.name}
                  <button
                    onClick={() => setSelectedMentions(selectedMentions.filter(m => m !== id))}
                    className="hover:text-blue-900"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              );
            })}
          </div>
        )}

        {/* Actions */}
        <div className="px-3 py-2 border-t border-gray-100 flex items-center justify-between bg-gray-50/30">
          <button
            onClick={() => setShowMentions(!showMentions)}
            className={cn(
              'flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors',
              showMentions ? 'bg-blue-100 text-blue-700' : 'text-muted-foreground hover:bg-gray-100 hover:text-gunmetal'
            )}
          >
            <AtSign className="w-3.5 h-3.5" />
            <span>Mention</span>
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs text-muted-foreground hover:text-gunmetal transition-colors"
            >
              Cancel
            </button>
            <Button
              onClick={handleSubmit}
              disabled={!text.trim()}
              size="sm"
              className="h-7 px-3 text-xs bg-gunmetal hover:bg-gunmetal/90"
            >
              <Send className="w-3 h-3 mr-1" />
              Post
            </Button>
          </div>
        </div>

        {/* Keyboard hint */}
        <div className="px-3 py-1.5 bg-gray-50 border-t border-gray-100 text-center">
          <span className="text-[10px] text-muted-foreground">
            Press <kbd className="px-1 py-0.5 bg-gray-200 rounded text-[9px] font-mono">⌘</kbd> + <kbd className="px-1 py-0.5 bg-gray-200 rounded text-[9px] font-mono">Enter</kbd> to post
          </span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// CanvasChart Component - Full-page forecast chart
// ============================================================================

interface CanvasChartProps {
  chartData: ChartDataPoint[];
  bufferThreshold: number;
  isLoading: boolean;
  showConfidence: boolean;
  showComments?: boolean;
  showInsights?: boolean;
  alerts?: Risk[];
  onAlertClick?: (alert: Risk) => void;
  comments: ChartComment[];
  onAddComment?: (comment: { text: string; mentions: string[]; weekNumber: number }) => void;
  isCommentDragging?: boolean;
  scenarioData?: ChartDataPoint[];
  scenarioName?: string;
  onClearScenario?: () => void;
}

interface ChartDataPoint {
  date: string;
  weekNumber: number;
  weekStart?: string;
  weekEnd?: string;
  position: number;
  bestCase: number;
  worstCase: number;
  cashIn: number;
  cashOut: number;
  confidence: string;
}

// Custom draggable tooltip for the forecast chart
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: ChartDataPoint;
  }>;
  label?: string;
}

function CustomChartTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;

  const formatCurrency = (value: number) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
    return `$${value.toFixed(0)}`;
  };

  const handleDragStart = (e: React.DragEvent) => {
    const weekData = {
      weekNumber: data.weekNumber,
      weekStart: data.weekStart,
      weekEnd: data.weekEnd,
      balance: data.position,
      income: data.cashIn,
      costs: data.cashOut,
    };
    e.dataTransfer.setData('application/json', JSON.stringify(weekData));
    e.dataTransfer.effectAllowed = 'copy';
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="bg-white/95 backdrop-blur-sm rounded-xl shadow-xl border border-gray-200 overflow-hidden cursor-grab active:cursor-grabbing min-w-[200px]"
    >
      {/* Header with week info and drag handle */}
      <div className="bg-gunmetal px-3 py-2 flex items-center justify-between">
        <div>
          <div className="text-white font-semibold text-sm">Week {data.weekNumber}</div>
          {data.weekStart && data.weekEnd && (
            <div className="text-white/60 text-[10px]">{data.weekStart} - {data.weekEnd}</div>
          )}
        </div>
        <div className="flex items-center gap-1 text-white/40">
          <GripVertical className="w-4 h-4" />
        </div>
      </div>

      {/* Metrics */}
      <div className="p-3 space-y-2">
        {/* Balance */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">Balance</span>
          <span className="text-sm font-semibold text-gunmetal">{formatCurrency(data.position)}</span>
        </div>

        {/* Income */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <ArrowDownRight className="w-3 h-3 text-green-500" />
            <span className="text-xs text-muted-foreground">Income</span>
          </div>
          <span className="text-sm font-medium text-green-600">+{formatCurrency(data.cashIn)}</span>
        </div>

        {/* Costs */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <ArrowUpRight className="w-3 h-3 text-red-500" />
            <span className="text-xs text-muted-foreground">Costs</span>
          </div>
          <span className="text-sm font-medium text-red-500">-{formatCurrency(data.cashOut)}</span>
        </div>
      </div>

      {/* Drag hint */}
      <div className="px-3 py-1.5 bg-lime/10 border-t border-lime/20">
        <div className="flex items-center gap-1.5 text-[10px] text-lime-700">
          <Sparkles className="w-3 h-3" />
          <span>Drag to AI chat to explore this week</span>
        </div>
      </div>
    </div>
  );
}

function CanvasChart({ chartData, bufferThreshold, isLoading, showConfidence, showComments = false, showInsights = false, alerts = [], onAlertClick, comments, onAddComment, isCommentDragging = false, scenarioData, scenarioName, onClearScenario }: CanvasChartProps) {
  const [hoveredPoint, setHoveredPoint] = useState<{ data: ChartDataPoint; x: number; y: number } | null>(null);
  const [newCommentPosition, setNewCommentPosition] = useState<NewCommentPosition | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Merge scenario data into chart data for Recharts
  const mergedChartData = useMemo(() => {
    if (!scenarioData) return chartData;
    const scenarioMap = new Map(scenarioData.map(d => [d.weekNumber, d.position]));
    return chartData.map(d => ({
      ...d,
      scenarioPosition: scenarioMap.get(d.weekNumber) ?? undefined,
    }));
  }, [chartData, scenarioData]);

  const formatCurrency = (value: number) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`;
    return `$${value.toFixed(0)}`;
  };

  // Handle drag over for comment tool
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    // Only accept comment tool drags
    if (e.dataTransfer.types.includes('application/comment-tool')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      setIsDragOver(true);
    }
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  // Handle drop for comment tool
  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);

    // Only handle comment tool drops
    if (!e.dataTransfer.types.includes('application/comment-tool')) return;
    if (!showComments || !onAddComment) return;

    const container = chartContainerRef.current;
    if (!container) return;

    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Calculate which week was dropped on based on x position
    // Account for chart margins (left: ~80px for Y axis, right: ~40px)
    const chartLeftMargin = 80;
    const chartRightMargin = 40;
    const chartWidth = rect.width - chartLeftMargin - chartRightMargin;
    const relativeX = x - chartLeftMargin;

    // Map x position to week number
    const totalWeeks = chartData.length || 13;
    const weekNumber = Math.max(1, Math.min(totalWeeks, Math.round((relativeX / chartWidth) * totalWeeks)));

    setNewCommentPosition({ x, y, weekNumber });
  };

  const handleAddComment = (comment: { text: string; mentions: string[]; weekNumber: number }) => {
    onAddComment?.(comment);
    setNewCommentPosition(null);
  };

  // Custom dot renderer with hover detection
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const renderCustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    const isHovered = hoveredPoint?.data?.weekNumber === payload?.weekNumber;

    return (
      <circle
        key={`dot-${payload?.weekNumber}`}
        cx={cx}
        cy={cy}
        r={isHovered ? 8 : 5}
        fill="#1C2127"
        stroke={isHovered ? '#fff' : 'none'}
        strokeWidth={isHovered ? 2 : 0}
        style={{ cursor: 'grab', transition: 'r 0.15s ease' }}
        onMouseEnter={() => setHoveredPoint({ data: payload, x: cx, y: cy })}
        onMouseLeave={() => setHoveredPoint(null)}
      />
    );
  };

  // Calculate pin position based on week number
  const getPinPosition = (weekNumber: number, offsetY: number = 0): { left: string; top: string; positionAbove: boolean } => {
    const totalWeeks = chartData.length || 13;
    const dataPoint = chartData.find(d => d.weekNumber === weekNumber);

    // Calculate horizontal position (percentage across chart area)
    // Account for chart margins (left: 80px for Y axis, right: 40px)
    const chartLeftMargin = 80;
    const chartRightMargin = 40;
    const leftPercent = ((weekNumber / totalWeeks) * 100);

    // Calculate vertical position based on the position value at that week
    if (dataPoint) {
      const maxValue = Math.max(...chartData.map(d => d.bestCase || d.position));
      const minValue = Math.min(...chartData.map(d => d.worstCase || d.position)) * 0.8;
      const range = maxValue - minValue;
      const topPercent = 100 - ((dataPoint.position - minValue) / range * 100);
      // If point is in bottom half of chart (topPercent > 50), show popover above
      const positionAbove = topPercent > 50;
      return {
        left: `calc(${chartLeftMargin}px + ${leftPercent}% - ${(chartLeftMargin + chartRightMargin) * leftPercent / 100}px)`,
        top: `calc(20px + ${(topPercent * 0.85) + offsetY}%)`,
        positionAbove,
      };
    }

    return { left: `${leftPercent}%`, top: '50%', positionAbove: false };
  };

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-center">
          <Skeleton className="w-16 h-16 rounded-full mx-auto mb-4" />
          <Skeleton className="w-32 h-4 mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div
      ref={chartContainerRef}
      className={cn(
        "relative w-full h-full transition-all duration-200",
        isCommentDragging && "cursor-copy",
        isDragOver && "ring-2 ring-blue-500 ring-inset bg-blue-50/20"
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Comment pins layer */}
      {showComments && (
        <div className="absolute inset-0 pointer-events-none z-20">
          {comments.map((comment) => {
            const position = getPinPosition(comment.weekNumber);
            return (
              <CommentPin
                key={comment.id}
                comment={comment}
                positionAbove={position.positionAbove}
                style={{
                  left: position.left,
                  top: position.top,
                  transform: 'translate(-50%, -100%)',
                  pointerEvents: 'auto',
                }}
              />
            );
          })}
        </div>
      )}

      {/* TAMI Insight pins layer */}
      {showInsights && (
        <div className="absolute inset-0 pointer-events-none z-20">
          {chartInsights.map((insight) => {
            // Offset insights slightly below the line to differentiate from comments
            const position = getPinPosition(insight.weekNumber, 8);
            return (
              <InsightPin
                key={insight.id}
                insight={insight}
                positionAbove={position.positionAbove}
                style={{
                  left: position.left,
                  top: position.top,
                  transform: 'translate(-50%, 0%)',
                  pointerEvents: 'auto',
                }}
              />
            );
          })}
        </div>
      )}

      {/* Alerts pins layer - shown with insights */}
      {showInsights && alerts.length > 0 && (
        <div className="absolute inset-0 pointer-events-none z-20">
          {alerts
            .filter(alert => alert.severity === 'urgent' || alert.severity === 'high')
            .map((alert) => {
              // Calculate week number from deadline, default to week 2 if no deadline
              const deadlineDate = alert.deadline ? new Date(alert.deadline) : null;
              const now = new Date();
              const weekNumber = deadlineDate
                ? Math.max(0, Math.min(12, Math.ceil((deadlineDate.getTime() - now.getTime()) / (7 * 24 * 60 * 60 * 1000))))
                : 2;
              // Offset alerts slightly above the line
              const position = getPinPosition(weekNumber, -12);
              return (
                <AlertPin
                  key={alert.id}
                  alert={alert}
                  positionAbove={position.positionAbove}
                  onClick={onAlertClick}
                  style={{
                    left: position.left,
                    top: position.top,
                    transform: 'translate(-50%, -100%)',
                    pointerEvents: 'auto',
                  }}
                />
              );
            })}
        </div>
      )}

      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={mergedChartData}
          margin={{ top: 20, right: 40, bottom: 20, left: 20 }}
        >
          <defs>
            <linearGradient id="canvasConfidenceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1C2127" stopOpacity={0.08} />
              <stop offset="100%" stopColor="#1C2127" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="0"
            stroke="#d1d5db"
            strokeOpacity={0.5}
            vertical={false}
            horizontal={true}
          />

          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            dy={10}
          />

          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickFormatter={formatCurrency}
            dx={-10}
            width={60}
          />

{/* Tooltip removed - using custom hover on dots only */}

          {/* Buffer threshold line */}
          <ReferenceLine
            y={bufferThreshold}
            stroke="#f59e0b"
            strokeDasharray="8 4"
            strokeWidth={2}
            label={{
              value: `Buffer ${formatCurrency(bufferThreshold)}`,
              position: 'right',
              fill: '#f59e0b',
              fontSize: 11,
            }}
          />

          {/* Confidence band */}
          {showConfidence && (
            <Area
              type="monotone"
              dataKey="bestCase"
              stroke="none"
              fill="url(#canvasConfidenceGradient)"
              fillOpacity={1}
            />
          )}

          {/* Best case line */}
          {showConfidence && (
            <Line
              type="monotone"
              dataKey="bestCase"
              stroke="#22c55e"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              activeDot={false}
            />
          )}

          {/* Worst case line */}
          {showConfidence && (
            <Line
              type="monotone"
              dataKey="worstCase"
              stroke="#ef4444"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              activeDot={false}
            />
          )}

          {/* Main forecast line */}
          <Line
            type="monotone"
            dataKey="position"
            stroke="#1C2127"
            strokeWidth={2.5}
            dot={renderCustomDot}
            activeDot={false}
          />

          {/* Scenario overlay line */}
          {scenarioData && (
            <Line
              type="monotone"
              dataKey="scenarioPosition"
              stroke="#8B5CF6"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
              activeDot={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Active scenario badge */}
      {scenarioName && onClearScenario && (
        <div className="absolute top-3 right-3 z-20 flex items-center gap-2 bg-white/90 backdrop-blur-sm border border-purple-200 rounded-lg px-3 py-1.5 shadow-sm">
          <div className="w-3 h-0.5 bg-purple-500 rounded" style={{ borderTop: '2px dashed #8B5CF6' }} />
          <span className="text-xs font-medium text-purple-700">{scenarioName}</span>
          <button
            onClick={onClearScenario}
            className="ml-1 text-purple-400 hover:text-purple-600 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Custom tooltip - only shows when hovering on dots */}
      {hoveredPoint && (
        <div
          className="absolute z-50 pointer-events-auto"
          data-tooltip
          style={{
            left: hoveredPoint.x,
            top: hoveredPoint.y,
            transform: 'translate(-50%, -100%) translateY(-12px)',
          }}
          onMouseEnter={() => setHoveredPoint(hoveredPoint)}
          onMouseLeave={() => setHoveredPoint(null)}
        >
          <CustomChartTooltip
            active={true}
            payload={[{ payload: hoveredPoint.data }]}
          />
        </div>
      )}

      {/* Add comment popup */}
      {newCommentPosition && showComments && (
        <AddCommentPopup
          position={newCommentPosition}
          onSubmit={handleAddComment}
          onClose={() => setNewCommentPosition(null)}
        />
      )}
    </div>
  );
}

// ============================================================================
// CollapsibleSidebar Component - Right sidebar with tabs
// ============================================================================

interface CollapsibleSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  alerts: Risk[];
  actions: Control[];
  activity: AgentActivityStats | null;
  rules: FinancialRule[];
  isLoading: boolean;
  onAlertClick?: (alert: Risk) => void;
}

function CollapsibleSidebar({
  isOpen,
  onToggle,
  activeTab,
  onTabChange,
  alerts,
  actions,
  activity,
  rules,
  isLoading,
  onAlertClick,
}: CollapsibleSidebarProps) {
  const urgentCount = alerts.filter((a) => a.severity === 'urgent').length;

  // Mock team members for display
  const teamMembers = [
    { initials: 'JD', color: 'bg-green-500', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' },
    { initials: 'AK', color: 'bg-amber-500', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face' },
    { initials: 'TS', color: 'bg-purple-500', avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=face' },
  ];

  return (
    <>
      {/* Toggle Button (visible when sidebar is closed) */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="fixed top-4 right-4 z-40 bg-white rounded-lg p-2 shadow-md border border-gray-200 hover:bg-gray-50 transition-colors"
        >
          <PanelLeft className="w-4 h-4 text-gunmetal/70" />
        </button>
      )}

      {/* Sidebar Panel */}
      <div
        className={cn(
          'fixed top-7 right-0 h-[calc(100%-1.75rem)] w-[320px] z-40 transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        <div className="h-full bg-white border-l border-gray-200 flex flex-col shadow-lg">
          {/* People, Notifications, Share Header */}
          <div className="px-4 py-3 border-b border-gray-200 bg-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1">
                {/* Toggle Button */}
                <button
                  onClick={onToggle}
                  className="p-1.5 rounded-md hover:bg-gray-100 transition-colors mr-2"
                >
                  <PanelRightClose className="w-4 h-4 text-gunmetal/70" />
                </button>

                {/* Team Avatars */}
                <div className="flex items-center -space-x-2">
                  {teamMembers.map((member, idx) => (
                    <Avatar key={idx} className={cn('w-7 h-7 border-2 border-white', member.color)}>
                      {member.avatar && <AvatarImage src={member.avatar} alt={member.initials} />}
                      <AvatarFallback className={cn('text-[10px] font-semibold text-white', member.color)}>
                        {member.initials}
                      </AvatarFallback>
                    </Avatar>
                  ))}
                </div>

                {/* Add Person Button */}
                <button className="w-7 h-7 rounded-full border-2 border-dashed border-gray-300 flex items-center justify-center ml-1 hover:border-gray-400 transition-colors">
                  <span className="text-gray-400 text-sm">+</span>
                </button>

                {/* Notification Bell */}
                <div className="ml-2">
                  <NotificationsDropdown />
                </div>
              </div>

              {/* Share Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" className="h-8 px-3 bg-gunmetal hover:bg-gunmetal/90 text-white text-xs font-medium gap-1.5">
                    <Upload className="w-3.5 h-3.5" />
                    Share
                    <ChevronDown className="w-3 h-3 ml-0.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  <DropdownMenuItem
                    className="flex items-start gap-3 p-3 cursor-pointer"
                    onClick={() => toast.info('Share Dashboard coming soon')}
                  >
                    <Users className="w-5 h-5 text-muted-foreground mt-0.5" />
                    <div>
                      <div className="font-medium text-sm">Share Dashboard</div>
                      <div className="text-xs text-muted-foreground">Invite team members to view or edit</div>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="flex items-start gap-3 p-3 cursor-pointer"
                    onClick={() => toast.info('Export Snapshot coming soon')}
                  >
                    <Download className="w-5 h-5 text-muted-foreground mt-0.5" />
                    <div>
                      <div className="font-medium text-sm">Export Snapshot</div>
                      <div className="text-xs text-muted-foreground">Download as PDF or image</div>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="flex items-start gap-3 p-3 cursor-pointer"
                    onClick={() => toast.info('Copy for Board Deck coming soon')}
                  >
                    <Copy className="w-5 h-5 text-muted-foreground mt-0.5" />
                    <div>
                      <div className="font-medium text-sm">Copy for Board Deck</div>
                      <div className="text-xs text-muted-foreground">Formatted summary for presentations</div>
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="flex items-start gap-3 p-3 cursor-pointer"
                    onClick={() => toast.info('Manage Access coming soon')}
                  >
                    <ShieldCheck className="w-5 h-5 text-muted-foreground mt-0.5" />
                    <div>
                      <div className="font-medium text-sm">Manage Access</div>
                      <div className="text-xs text-muted-foreground">See who has access to this dashboard</div>
                    </div>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Tabs */}
          <div className="px-3 py-2 flex gap-1 border-b border-gray-100 bg-gray-50/30">
            {[
              { id: 'alerts' as const, label: 'Alerts', count: urgentCount },
              { id: 'activity' as const, label: 'Activity', count: null },
              { id: 'rules' as const, label: 'Rules', count: null },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={cn(
                  'flex-1 px-3 py-2 rounded-md text-xs font-medium transition-all',
                  activeTab === tab.id
                    ? 'bg-gunmetal text-white shadow-sm'
                    : 'text-gunmetal/50 hover:text-gunmetal hover:bg-white'
                )}
              >
                {tab.label}
                {tab.count !== null && tab.count > 0 && (
                  <span className={cn(
                    'ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] font-semibold',
                    activeTab === tab.id ? 'bg-white/20' : 'bg-tomato text-white'
                  )}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Content */}
          <ScrollArea className="flex-1">
            <div className="p-4">
              {activeTab === 'alerts' && (
                <AlertsContent alerts={alerts} actions={actions} isLoading={isLoading} onAlertClick={onAlertClick} />
              )}
              {activeTab === 'activity' && (
                <ActivityContent activity={activity} isLoading={isLoading} />
              )}
              {activeTab === 'rules' && (
                <RulesContent rules={rules} isLoading={isLoading} />
              )}
            </div>
          </ScrollArea>
        </div>
      </div>
    </>
  );
}

// Alerts Tab Content
const INITIAL_VISIBLE_ALERTS = 3;

function AlertsContent({ alerts, actions, isLoading, onAlertClick }: { alerts: Risk[]; actions: Control[]; isLoading: boolean; onAlertClick?: (alert: Risk) => void }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  const urgentAlerts = alerts.filter((a) => a.severity === 'urgent' || a.severity === 'high');
  const pendingActions = actions.filter((a) => a.state === 'pending');

  // Progressive disclosure: limit visible alerts
  const totalItems = urgentAlerts.length + pendingActions.length;
  const visibleAlerts = isExpanded ? urgentAlerts : urgentAlerts.slice(0, INITIAL_VISIBLE_ALERTS);
  const visibleActions = isExpanded ? pendingActions : pendingActions.slice(0, Math.max(0, INITIAL_VISIBLE_ALERTS - urgentAlerts.length));
  const hiddenCount = totalItems - INITIAL_VISIBLE_ALERTS;

  return (
    <div className="space-y-4">
      {/* Recent Activity Summary */}
      <div className="glass rounded-xl p-3 text-xs">
        <div className="flex items-center justify-between text-muted-foreground mb-2">
          <span>SINCE YESTERDAY</span>
          <span>{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
            <span className="text-gunmetal">Cash received</span>
            <span className="ml-auto font-medium text-green-600">+$24,500</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-red-500" />
            <span className="text-gunmetal">Expenses paid</span>
            <span className="ml-auto font-medium text-red-500">-$8,200</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-green-500" />
            <span className="text-gunmetal">Runway change</span>
            <span className="ml-auto font-medium text-green-600">+0.5w</span>
          </div>
        </div>
      </div>

      {/* Requires Decision */}
      {(urgentAlerts.length > 0 || pendingActions.length > 0) && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-xs font-semibold text-gunmetal uppercase tracking-wide">
              Requires Decision ({urgentAlerts.length + pendingActions.length})
            </span>
          </div>

          <div className="space-y-2">
            {visibleAlerts.map((alert) => (
              <button
                key={alert.id}
                onClick={() => onAlertClick?.(alert)}
                className="w-full text-left p-3 rounded-xl border border-red-200 bg-red-50/50 hover:bg-red-50 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm text-gunmetal truncate">
                      {alert.title}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {alert.primary_driver}
                    </div>
                    <div className="text-xs text-red-500 mt-1">
                      {alert.impact_statement || 'High priority'}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                </div>
              </button>
            ))}

            {visibleActions.map((action) => (
              <button
                key={action.id}
                className="w-full text-left p-3 rounded-xl border border-amber-200 bg-amber-50/50 hover:bg-amber-50 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <Clock className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm text-gunmetal truncate">
                      {action.name}
                    </div>
                    <div className="text-xs text-muted-foreground truncate">
                      {action.why_it_exists}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                </div>
              </button>
            ))}

            {/* Expand/Collapse Button */}
            {hiddenCount > 0 && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-center gap-1.5 py-2 text-xs text-muted-foreground hover:text-gunmetal hover:bg-white/50 rounded-lg transition-colors"
              >
                {isExpanded ? (
                  <>
                    <ChevronDown className="w-3.5 h-3.5 rotate-180" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-3.5 h-3.5" />
                    Show {hiddenCount} more
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      )}

      {urgentAlerts.length === 0 && pendingActions.length === 0 && (
        <div className="text-center py-8 text-muted-foreground text-sm">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-500" />
          All caught up! No urgent items.
        </div>
      )}
    </div>
  );
}

// Activity Types and Config (matching notification centre)
type SidebarActivityType = 'approval' | 'mention' | 'shared' | 'reconciliation';

interface SidebarActivity {
  id: string;
  type: SidebarActivityType;
  title: string;
  description: string;
  timestamp: string;
  read: boolean;
  actor?: {
    name: string;
  };
}

const sidebarActivityTypeConfig = {
  approval: {
    icon: CheckSquare,
    bgClass: 'bg-amber-500/10',
    borderClass: 'border-amber-500/20',
    textClass: 'text-amber-600',
    label: 'Pending Approvals',
  },
  mention: {
    icon: AtSign,
    bgClass: 'bg-sky-500/10',
    borderClass: 'border-sky-500/20',
    textClass: 'text-sky-600',
    label: 'Mentions',
  },
  shared: {
    icon: Share2,
    bgClass: 'bg-purple-500/10',
    borderClass: 'border-purple-500/20',
    textClass: 'text-purple-600',
    label: 'Shared With You',
  },
  reconciliation: {
    icon: ArrowRightLeft,
    bgClass: 'bg-lime/10',
    borderClass: 'border-lime/20',
    textClass: 'text-lime-700',
    label: 'Reconciliation',
  },
};

// Mock activities (matching notification centre data)
const mockSidebarActivities: SidebarActivity[] = [
  {
    id: 'act-1',
    type: 'approval',
    title: 'Payment batch ready',
    description: '3 vendor payments totaling $12,450 need your approval before Friday',
    timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    read: false,
    actor: { name: 'TAMI' },
  },
  {
    id: 'act-2',
    type: 'mention',
    title: 'Sarah mentioned you',
    description: 'in "Q2 Hiring Scenario" - "Can you review the salary assumptions?"',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    read: false,
    actor: { name: 'Sarah Chen' },
  },
  {
    id: 'act-3',
    type: 'reconciliation',
    title: 'Transaction needs review',
    description: 'Bank payment of $8,200 matched to RetailCo invoice with 5% variance',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
    read: false,
  },
];

function formatSidebarTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// Activity Card for sidebar (simplified version without drag)
function SidebarActivityCard({ activity }: { activity: SidebarActivity }) {
  const config = sidebarActivityTypeConfig[activity.type];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'relative p-3 rounded-xl border transition-all group',
        activity.read ? 'bg-white/50 opacity-70' : 'bg-white',
        config.borderClass
      )}
    >
      <div className="flex gap-3">
        {/* Icon */}
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
            config.bgClass,
            'border',
            config.borderClass
          )}
        >
          <Icon className={cn('w-4 h-4', config.textClass)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {!activity.read && (
                <span className={cn('w-2 h-2 rounded-full flex-shrink-0', config.textClass.replace('text-', 'bg-'))} />
              )}
              <span className="text-sm font-medium text-gunmetal truncate">
                {activity.title}
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              {formatSidebarTimeAgo(activity.timestamp)}
            </span>
          </div>

          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
            {activity.description}
          </p>

          {/* Actor badge */}
          {activity.actor && (
            <div className="flex items-center gap-1.5 mt-2">
              <div className="w-4 h-4 rounded-full bg-gray-100 flex items-center justify-center">
                <User className="w-2.5 h-2.5 text-gray-400" />
              </div>
              <span className="text-xs text-muted-foreground">
                {activity.actor.name}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Activity Tab Content (matching notification centre style)
function ActivityContent({ activity, isLoading }: { activity: AgentActivityStats | null; isLoading: boolean }) {
  const [activities] = useState<SidebarActivity[]>(mockSidebarActivities);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-3 rounded-xl border border-gray-100">
            <div className="flex gap-3">
              <Skeleton className="w-8 h-8 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <div className="flex items-center gap-1.5">
                  <Skeleton className="w-4 h-4 rounded-full" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
          <CheckCircle2 className="w-6 h-6 text-gray-400" />
        </div>
        <h3 className="text-sm font-semibold text-gunmetal mb-1">All caught up!</h3>
        <p className="text-xs text-muted-foreground max-w-[250px]">
          No pending activity. Team mentions, shared items, and approvals will appear here.
        </p>
      </div>
    );
  }

  // Group activities by type
  const unreadActivities = activities.filter((a) => !a.read);
  const readActivities = activities.filter((a) => a.read);

  const groupedUnread = unreadActivities.reduce((acc, activity) => {
    if (!acc[activity.type]) {
      acc[activity.type] = [];
    }
    acc[activity.type].push(activity);
    return acc;
  }, {} as Record<SidebarActivityType, SidebarActivity[]>);

  const typeOrder: SidebarActivityType[] = ['approval', 'mention', 'reconciliation', 'shared'];

  return (
    <div className="space-y-4">
      {/* Unread activities grouped by type */}
      {typeOrder.map((type) => {
        const group = groupedUnread[type];
        if (!group || group.length === 0) return null;

        const config = sidebarActivityTypeConfig[type];

        return (
          <div key={type}>
            <div className={cn('px-3 py-1.5 rounded-lg mb-2', config.bgClass)}>
              <div className="flex items-center gap-2">
                <Activity className={cn('w-3.5 h-3.5', config.textClass)} />
                <span className={cn('text-xs font-medium uppercase tracking-wide', config.textClass)}>
                  {config.label}
                </span>
                <span className={cn('text-xs', config.textClass)}>
                  ({group.length})
                </span>
              </div>
            </div>
            <div className="space-y-2">
              {group.map((activityItem) => (
                <SidebarActivityCard
                  key={activityItem.id}
                  activity={activityItem}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Read activities */}
      {readActivities.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-gray-50">
            <div className="flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Earlier
              </span>
              <span className="text-xs text-gray-400">
                ({readActivities.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {readActivities.map((activityItem) => (
              <SidebarActivityCard
                key={activityItem.id}
                activity={activityItem}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Rule Progress Types (matching notification centre)
type SidebarRuleType = 'cash_buffer' | 'tax_vat_reserve' | 'payroll' | 'receivables' | 'unusual_activity';
type SidebarRuleStatus = 'healthy' | 'warning' | 'triggered' | 'paused';

interface SidebarRuleProgress {
  id: string;
  name: string;
  ruleType: SidebarRuleType;
  status: SidebarRuleStatus;
  progressPercentage: number;
  statusMessage: string;
}

// Rule type icons
const SIDEBAR_RULE_ICONS: Record<SidebarRuleType, typeof Wallet> = {
  cash_buffer: Wallet,
  tax_vat_reserve: Receipt,
  payroll: Users,
  receivables: FileText,
  unusual_activity: TrendingUp,
};

// Status labels
const sidebarStatusLabels: Record<SidebarRuleStatus, string> = {
  healthy: 'Healthy',
  warning: 'Warning',
  triggered: 'Triggered',
  paused: 'Paused',
};

// Status styles
function getSidebarStatusStyles(status: SidebarRuleStatus): {
  bgClass: string;
  textClass: string;
  dotClass: string;
  barClass: string;
} {
  switch (status) {
    case 'healthy':
      return {
        bgClass: 'bg-lime/20',
        textClass: 'text-lime-dark',
        dotClass: 'bg-lime',
        barClass: 'bg-lime',
      };
    case 'warning':
      return {
        bgClass: 'bg-amber-100',
        textClass: 'text-amber-700',
        dotClass: 'bg-amber-500',
        barClass: 'bg-amber-500',
      };
    case 'triggered':
      return {
        bgClass: 'bg-tomato/20',
        textClass: 'text-tomato',
        dotClass: 'bg-tomato',
        barClass: 'bg-tomato',
      };
    case 'paused':
      return {
        bgClass: 'bg-gray-100',
        textClass: 'text-gray-500',
        dotClass: 'bg-gray-400',
        barClass: 'bg-gray-400',
      };
  }
}

// Mock rule progress data
const mockSidebarRuleProgress: SidebarRuleProgress[] = [
  {
    id: 'rule-1',
    name: 'Cash Buffer Alert',
    ruleType: 'cash_buffer',
    status: 'healthy',
    progressPercentage: 145,
    statusMessage: '145% of buffer maintained',
  },
  {
    id: 'rule-2',
    name: 'VAT Reserve',
    ruleType: 'tax_vat_reserve',
    status: 'warning',
    progressPercentage: 82,
    statusMessage: '18% below target',
  },
  {
    id: 'rule-3',
    name: 'Payroll Coverage',
    ruleType: 'payroll',
    status: 'healthy',
    progressPercentage: 100,
    statusMessage: 'Fully covered for next pay date',
  },
];

// Rule Progress Card for sidebar
function SidebarRuleProgressCard({ ruleProgress }: { ruleProgress: SidebarRuleProgress }) {
  const styles = getSidebarStatusStyles(ruleProgress.status);
  const Icon = SIDEBAR_RULE_ICONS[ruleProgress.ruleType];
  const displayProgress = Math.min(Math.max(ruleProgress.progressPercentage, 0), 100);
  const isExceeding = ruleProgress.progressPercentage > 100;

  return (
    <div className="relative p-3 rounded-xl border border-gray-100 bg-white transition-all group">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center">
            <Icon className="h-4 w-4 text-gunmetal" />
          </div>
          <span className="text-sm font-medium text-gunmetal">{ruleProgress.name}</span>
        </div>

        {/* Status Badge */}
        <div
          className={cn(
            'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
            styles.bgClass,
            styles.textClass
          )}
        >
          <div className={cn('w-1.5 h-1.5 rounded-full', styles.dotClass)} />
          {sidebarStatusLabels[ruleProgress.status]}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1.5">
        <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden relative">
          <div
            className={cn('h-full rounded-full transition-all duration-500', styles.barClass)}
            style={{ width: `${displayProgress}%` }}
          />
          {isExceeding && (
            <div className="absolute right-0 top-0 h-full w-1 bg-lime-600 animate-pulse" />
          )}
        </div>

        <div className="flex justify-between items-center text-xs">
          <span className="text-muted-foreground">{ruleProgress.statusMessage}</span>
          <span className={cn('font-medium', styles.textClass)}>
            {ruleProgress.progressPercentage.toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

// Rules Tab Content (matching notification centre style)
function RulesContent({ rules, isLoading }: { rules: FinancialRule[]; isLoading: boolean }) {
  // Use mock data for display
  const ruleProgressList = mockSidebarRuleProgress;

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-3 rounded-xl border border-gray-100">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Skeleton className="w-8 h-8 rounded-lg" />
                <Skeleton className="h-4 w-32" />
              </div>
              <Skeleton className="h-6 w-20 rounded-full" />
            </div>
            <Skeleton className="h-2.5 w-full rounded-full mb-1.5" />
            <div className="flex justify-between">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-3 w-10" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (rules.length === 0 && ruleProgressList.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
          <Gauge className="w-6 h-6 text-gray-400" />
        </div>
        <h3 className="text-sm font-semibold text-gunmetal mb-1">No rules set up</h3>
        <p className="text-xs text-muted-foreground max-w-[250px] mb-4">
          Create financial safety rules to monitor your cash flow and get alerts when thresholds are approached.
        </p>
        <Button size="sm" className="gap-1.5">
          <Plus className="w-4 h-4" />
          Create a Rule
        </Button>
      </div>
    );
  }

  // Group by status
  const triggeredRules = ruleProgressList.filter((rp) => rp.status === 'triggered');
  const warningRules = ruleProgressList.filter((rp) => rp.status === 'warning');
  const healthyRules = ruleProgressList.filter((rp) => rp.status === 'healthy');
  const pausedRules = ruleProgressList.filter((rp) => rp.status === 'paused');

  return (
    <div className="space-y-4">
      {/* Triggered Section */}
      {triggeredRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-tomato/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-tomato" />
              <span className="text-xs font-medium uppercase tracking-wide text-tomato">
                Triggered ({triggeredRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {triggeredRules.map((rp) => (
              <SidebarRuleProgressCard key={rp.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}

      {/* Warning Section */}
      {warningRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-amber-500/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-xs font-medium uppercase tracking-wide text-amber-600">
                Warning ({warningRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {warningRules.map((rp) => (
              <SidebarRuleProgressCard key={rp.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}

      {/* Healthy Section */}
      {healthyRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-lime/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-lime" />
              <span className="text-xs font-medium uppercase tracking-wide text-lime-700">
                Healthy ({healthyRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {healthyRules.map((rp) => (
              <SidebarRuleProgressCard key={rp.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}

      {/* Paused Section */}
      {pausedRules.length > 0 && (
        <div>
          <div className="px-3 py-1.5 rounded-lg mb-2 bg-gray-100">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-gray-400" />
              <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Paused ({pausedRules.length})
              </span>
            </div>
          </div>
          <div className="space-y-2">
            {pausedRules.map((rp) => (
              <SidebarRuleProgressCard key={rp.id} ruleProgress={rp} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ForecastCanvas() {
  const { user } = useAuth();
  const { sendMessage, open: openTAMI } = useTAMI();

  // Data state
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [cashPosition, setCashPosition] = useState<CashPositionResponse | null>(null);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [alerts, setAlerts] = useState<Risk[]>([]);
  const [actions, setActions] = useState<Control[]>([]);
  const [activity, setActivity] = useState<AgentActivityStats | null>(null);

  // UI state
  const [timeRange, setTimeRange] = useState<TimeRange>('13w');
  const [showConfidence, setShowConfidence] = useState(false);
  const [showComments, setShowComments] = useState(true);
  const [showInsights, setShowInsights] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isCommentDragging, setIsCommentDragging] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<SidebarTab>('alerts');
  const [selectedAlert, setSelectedAlert] = useState<CanvasAlert | null>(null);

  // Scenarios state
  const [suggestedScenarios, setSuggestedScenarios] = useState<SuggestedScenario[]>([]);
  const [isScenariosLoading, setIsScenariosLoading] = useState(false);
  const [showManualScenarioModal, setShowManualScenarioModal] = useState(false);
  const [appliedScenario, setAppliedScenario] = useState<{
    name: string;
    chartData: ChartDataPoint[];
  } | null>(null);
  const [scenarioLoading, setScenarioLoading] = useState(false);

  // Comments state - initialize with mock data
  const [comments, setComments] = useState<ChartComment[]>(chartComments);

  // Parse weeks from time range
  const weeks = useMemo(() => {
    const map = { '13w': 13, '26w': 26, '52w': 52 };
    return map[timeRange];
  }, [timeRange]);

  // Calculate metrics from API data
  const metrics: CanvasMetrics = useMemo(() => {
    const cashPositionValue = cashPosition ? parseFloat(cashPosition.total_starting_cash) : 0;
    const runwayWeeks = forecast?.summary?.runway_weeks ?? 0;

    let income30d = 0;
    let expenses30d = 0;
    let prevIncome = 0;
    let prevExpenses = 0;

    if (forecast?.weeks) {
      forecast.weeks.slice(0, 4).forEach((week) => {
        income30d += parseFloat(week.cash_in || '0');
        expenses30d += parseFloat(week.cash_out || '0');
      });

      forecast.weeks.slice(4, 8).forEach((week) => {
        prevIncome += parseFloat(week.cash_in || '0');
        prevExpenses += parseFloat(week.cash_out || '0');
      });
    }

    const calcTrend = (current: number, previous: number): TrendData => {
      if (previous === 0) return { direction: 'flat', percent: 0 };
      const percentChange = ((current - previous) / previous) * 100;
      if (Math.abs(percentChange) < 1) return { direction: 'flat', percent: 0 };
      return {
        direction: percentChange > 0 ? 'up' : 'down',
        percent: Math.abs(percentChange),
      };
    };

    const prevRunway = runwayWeeks > 0 ? runwayWeeks + 1 : 0;
    const runwayTrend = calcTrend(runwayWeeks, prevRunway);

    return {
      cashPosition: cashPositionValue,
      income30d,
      expenses30d,
      runwayWeeks,
      cashSource: cashPosition?.accounts?.[0]?.account_name || 'Bank',
      lastUpdated: '2 min ago',
      trends: {
        cashPosition: calcTrend(cashPositionValue, cashPositionValue * 0.95),
        income: calcTrend(income30d, prevIncome),
        expenses: calcTrend(expenses30d, prevExpenses),
        runway: runwayTrend,
      },
    };
  }, [cashPosition, forecast]);

  // Format KPI values
  const kpiData = useMemo(() => {
    const formatCurrency = (value: number) => {
      if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
      if (value >= 1000) return `$${Math.round(value / 1000)}K`;
      return `$${value.toFixed(0)}`;
    };

    const cashTrend = metrics.trends?.cashPosition;

    return {
      currentPosition: formatCurrency(metrics.cashPosition),
      runway: `${metrics.runwayWeeks}w`,
      bufferStatus: metrics.runwayWeeks >= 12 ? 'Safe' : metrics.runwayWeeks >= 8 ? 'Watch' : 'Low',
      trend: cashTrend?.direction === 'up' ? 'up' as const : cashTrend?.direction === 'down' ? 'down' as const : undefined,
      trendValue: cashTrend?.percent ? `${cashTrend.percent.toFixed(1)}%` : undefined,
    };
  }, [metrics]);

  // Helper function to calculate week date range
  const getWeekDateRange = (weekNumber: number): { weekStart: string; weekEnd: string } => {
    const today = new Date();
    const startOfCurrentWeek = new Date(today);
    startOfCurrentWeek.setDate(today.getDate() - today.getDay() + 1);

    const weekStart = new Date(startOfCurrentWeek);
    weekStart.setDate(weekStart.getDate() + (weekNumber - 1) * 7);

    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);

    const formatDate = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return {
      weekStart: formatDate(weekStart),
      weekEnd: formatDate(weekEnd),
    };
  };

  // Transform forecast weeks to chart data points
  const transformWeeksToChartData = useCallback((weeks: ForecastWeek[]): ChartDataPoint[] => {
    return weeks.map((week, index) => {
      const expected = parseFloat(week.ending_balance);
      const uncertaintyFactor = 1 + index * 0.02;
      const variance = expected * 0.15 * uncertaintyFactor;
      const { weekStart, weekEnd } = getWeekDateRange(week.week_number);

      return {
        date: `Week ${week.week_number}`,
        weekNumber: week.week_number,
        weekStart,
        weekEnd,
        position: expected,
        bestCase: expected + variance,
        worstCase: Math.max(0, expected - variance),
        cashIn: parseFloat(week.cash_in),
        cashOut: parseFloat(week.cash_out),
        confidence: index < 4 ? 'high' : index < 8 ? 'medium' : 'low',
      };
    });
  }, []);

  // Transform forecast to chart data
  const chartData = useMemo(() => {
    if (!forecast?.weeks) return [];
    return transformWeeksToChartData(forecast.weeks);
  }, [forecast, transformWeeksToChartData]);

  // Buffer threshold from rules
  const bufferThreshold = useMemo(() => {
    const bufferRule = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
    const months = bufferRule?.threshold_config?.months;
    if (typeof months === 'number' && months > 0) {
      const monthlyBurn = (metrics.expenses30d / 4) * 4.33;
      return monthlyBurn * months;
    }
    return 50000;
  }, [rules, metrics.expenses30d]);

  // Register page context for TAMI
  useTAMIPageContext({
    page: 'canvas',
    pageData: {
      timeRange,
      runwayWeeks: metrics.runwayWeeks,
      cashPosition: metrics.cashPosition,
    },
  });

  // Fetch all data
  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [forecastData, cashData, rulesData, risksResponse, controlsResponse, activityData] = await Promise.all([
          getForecast(user.id, weeks).catch(() => null),
          getCashPosition(user.id).catch(() => null),
          getRules(user.id).catch(() => []),
          getRisks().catch(() => ({ risks: [], total_count: 0 })),
          getControls().catch(() => ({ controls: [], total_count: 0 })),
          getAgentActivity(24).catch(() => null),
        ]);

        setForecast(forecastData);
        setCashPosition(cashData);
        setRules(rulesData);
        setAlerts(risksResponse.risks);
        setActions(controlsResponse.controls);
        setActivity(activityData);
      } catch (error) {
        console.error('Failed to fetch canvas data:', error);
        toast.error('Failed to load forecast data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user, weeks]);

  // Fetch suggested scenarios
  useEffect(() => {
    if (!user) return;

    const getImpactDirection = (impact: string | undefined): 'positive' | 'negative' | 'neutral' => {
      if (!impact) return 'neutral';
      if (impact.startsWith('+')) return 'positive';
      if (impact.startsWith('-')) return 'negative';
      return 'neutral';
    };

    const fetchScenarios = async () => {
      setIsScenariosLoading(true);
      try {
        const response = await getScenarioSuggestions(user.id);
        // Transform backend response to SuggestedScenario format
        const scenarios: SuggestedScenario[] = response.suggestions.map((s, index) => ({
          id: `suggestion-${index}`,
          name: s.name,
          description: s.description || s.risk_context || 'Explore how this scenario impacts your runway',
          impact: s.buffer_impact || 'Impact TBD',
          impactDirection: getImpactDirection(s.buffer_impact),
          type: s.scenario_type.includes('loss') || s.scenario_type.includes('delay') ? 'revenue_loss' as const :
                s.scenario_type.includes('gain') ? 'revenue_gain' as const :
                s.scenario_type.includes('expense') || s.scenario_type.includes('hiring') ? 'expense' as const :
                'delay' as const,
          scenario_type: s.scenario_type,
          prefill_params: s.prefill_params,
        }));
        setSuggestedScenarios(scenarios);
      } catch (error) {
        console.error('Failed to fetch scenario suggestions:', error);
        // Set fallback scenarios on error
        setSuggestedScenarios([
          { id: '1', name: 'Hire Product Designer', description: 'Growing team may require design support', impact: '-$8,500/mo', impactDirection: 'negative', type: 'expense' },
          { id: '2', name: 'Lose RetailCo', description: 'Your largest client represents 35% of revenue', impact: '-$45,000/mo', impactDirection: 'negative', type: 'revenue_loss' },
          { id: '3', name: 'TechCorp pays 30 days late', description: 'Based on their historical payment patterns', impact: '-$32K runway', impactDirection: 'negative', type: 'delay' },
          { id: '4', name: 'Win Enterprise deal', description: 'Pipeline opportunity in final negotiations', impact: '+$120,000', impactDirection: 'positive', type: 'revenue_gain' },
        ]);
      } finally {
        setIsScenariosLoading(false);
      }
    };

    fetchScenarios();
  }, [user]);

  // Handle AI input submit
  const handleAISubmit = useCallback(
    async (message: string) => {
      if (!message.trim()) return;
      openTAMI();
      await sendMessage(message);
    },
    [sendMessage, openTAMI]
  );

  // Handle alert click - convert Risk to CanvasAlert and open popup
  const handleAlertClick = useCallback((risk: Risk) => {
    const canvasAlert: CanvasAlert = {
      id: risk.id,
      tier: risk.severity === 'urgent' || risk.severity === 'high' ? 'act-now' : 'monitor',
      type: risk.detection_type || 'general',
      title: risk.title,
      subtitle: risk.primary_driver || '',
      body: risk.context_bullets?.join(' ') || '',
      severity: risk.severity,
      impact: risk.impact_statement || undefined,
      dueDate: risk.due_horizon_label || undefined,
    };
    setSelectedAlert(canvasAlert);
  }, []);

  // Handle adding a new comment to the chart
  const handleAddComment = useCallback((newComment: { text: string; mentions: string[]; weekNumber: number }) => {
    // Get display name from email or use fallback
    const displayName = user?.email?.split('@')[0] || 'You';
    const initials = displayName.slice(0, 2).toUpperCase();

    const comment: ChartComment = {
      id: `comment-${Date.now()}`,
      weekNumber: newComment.weekNumber,
      author: {
        name: displayName,
        initials: initials,
        color: 'bg-blue-500',
      },
      text: newComment.text,
      timestamp: 'Just now',
    };
    setComments(prev => [...prev, comment]);
    toast.success('Comment added', {
      description: `Added to Week ${newComment.weekNumber}`,
    });
  }, [user]);

  // Keyboard shortcut for AI input focus
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const aiInput = document.querySelector<HTMLInputElement>('[data-ai-input]');
        aiInput?.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handle applying a scenario
  const handleApplyScenario = useCallback(async (scenario: SuggestedScenario) => {
    if (!user?.id) return;
    setScenarioLoading(true);
    try {
      // Split prefill_params: scope keys (client_id, expense_bucket_id) go in scope_config,
      // everything else goes in parameters (the engine reads them from different places)
      const prefill = scenario.prefill_params || {};
      const scopeKeys = ['client_id', 'expense_bucket_id'];
      const scopeConfig: Record<string, unknown> = {};
      const parameters: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(prefill)) {
        if (scopeKeys.includes(key)) {
          scopeConfig[key] = value;
        } else {
          parameters[key] = value;
        }
      }

      const newScenario = await createScenario({
        user_id: user.id,
        name: scenario.name,
        scenario_type: scenario.scenario_type as ScenarioType || 'client_loss',
        entry_path: 'tamio_suggested',
        scope_config: scopeConfig,
        parameters,
      });
      await buildScenario(newScenario.id);
      const comparison = await getScenarioForecast(newScenario.id);
      const scenarioChartData = transformWeeksToChartData(comparison.scenario_forecast.weeks);
      setAppliedScenario({ name: scenario.name, chartData: scenarioChartData });
      toast.success(`Scenario "${scenario.name}" applied`, {
        description: `Impact: ${scenario.impact}`,
      });
    } catch (error) {
      console.error('Failed to apply scenario:', error);
      toast.error('Failed to apply scenario');
    } finally {
      setScenarioLoading(false);
    }
  }, [user?.id, transformWeeksToChartData]);

  // Handle building a custom scenario
  const handleBuildScenario = useCallback(async (params: ManualScenarioParams) => {
    if (!user?.id) return;
    setScenarioLoading(true);
    try {
      const newScenario = await createScenario({
        user_id: user.id,
        name: params.name,
        scenario_type: params.type,
        entry_path: 'user_defined',
        scope_config: { effective_date: params.effectiveDate },
        parameters: params.params,
      });
      await buildScenario(newScenario.id);
      const comparison = await getScenarioForecast(newScenario.id);
      const scenarioChartData = transformWeeksToChartData(comparison.scenario_forecast.weeks);
      setAppliedScenario({ name: params.name, chartData: scenarioChartData });
      setShowManualScenarioModal(false);
      toast.success(`Scenario "${params.name}" applied`);
    } catch (error) {
      console.error('Failed to build scenario:', error);
      toast.error('Failed to create scenario');
    } finally {
      setScenarioLoading(false);
    }
  }, [user?.id, transformWeeksToChartData]);

  return (
    <div className="relative h-[calc(100vh-120px)] -m-6 overflow-hidden">
      {/* Compact KPI Strip */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
        <CompactKPI
          label="Position"
          value={kpiData.currentPosition}
          trend={kpiData.trend}
          trendValue={kpiData.trendValue}
        />
        <CompactKPI label="Runway" value={kpiData.runway} />
        <CompactKPI
          label="Buffer"
          value={kpiData.bufferStatus}
          trend={kpiData.bufferStatus === 'Safe' ? 'up' : kpiData.bufferStatus === 'Low' ? 'down' : undefined}
        />
      </div>

      {/* Full Canvas Chart */}
      <div
        className={cn(
          'absolute inset-0 pt-24 pb-20 transition-all duration-300',
          sidebarOpen ? 'pr-[320px]' : 'pr-0'
        )}
      >
        <CanvasChart
          chartData={chartData}
          bufferThreshold={bufferThreshold}
          isLoading={isLoading}
          showConfidence={showConfidence}
          showComments={showComments}
          showInsights={showInsights}
          alerts={alerts}
          onAlertClick={handleAlertClick}
          comments={comments}
          onAddComment={handleAddComment}
          isCommentDragging={isCommentDragging}
          scenarioData={appliedScenario?.chartData}
          scenarioName={appliedScenario?.name}
          onClearScenario={appliedScenario ? () => setAppliedScenario(null) : undefined}
        />
      </div>

      {/* TAMI Chat Bar */}
      <TAMIChatBar onSend={handleAISubmit} isLoading={isLoading} onCommentDrag={setIsCommentDragging} />

      {/* Canvas Toolbar */}
      <CanvasToolbar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        showConfidence={showConfidence}
        onToggleConfidence={() => setShowConfidence(!showConfidence)}
        showComments={showComments}
        onToggleComments={() => setShowComments(!showComments)}
        showInsights={showInsights}
        onToggleInsights={() => setShowInsights(!showInsights)}
        alertCount={alerts.filter(a => a.severity === 'urgent' || a.severity === 'high').length}
        suggestedScenarios={suggestedScenarios}
        onApplyScenario={handleApplyScenario}
        onBuildCustomScenario={() => setShowManualScenarioModal(true)}
        isScenariosLoading={isScenariosLoading}
        sidebarOpen={sidebarOpen}
      />

      {/* Manual Scenario Modal */}
      <ManualScenarioModal
        isOpen={showManualScenarioModal}
        onClose={() => setShowManualScenarioModal(false)}
        onBuild={handleBuildScenario}
      />

      {/* Collapsible Sidebar */}
      <CollapsibleSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        alerts={alerts}
        actions={actions}
        activity={activity}
        rules={rules}
        isLoading={isLoading}
        onAlertClick={handleAlertClick}
      />

      {/* Alert Detail Popup */}
      {selectedAlert && (
        <AlertDetailPopup
          alert={selectedAlert}
          isOpen={!!selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}
    </div>
  );
}
