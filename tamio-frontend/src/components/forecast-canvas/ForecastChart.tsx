import { useMemo, useState, useRef, useCallback } from 'react';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { AlertTriangle, X, TrendingUp, TrendingDown, DollarSign, Calendar, ArrowRight, MessageCircle, Sparkles, Lightbulb, ShieldAlert, Zap, Check, Send, AtSign, Users, Plus, Bell, Clock, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Tooltip as RadixTooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ChartToolbar } from './ChartToolbar';
import type { ScenarioItem } from './ScenarioDropdown';
import { cn } from '@/lib/utils';
import type { LayerToggle, TimeRange } from '@/pages/ForecastCanvas';

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

interface AppliedScenario {
  id: string;
  name: string;
}

// Scenario chart data point (simplified from ChartDataPoint)
interface ScenarioDataPoint {
  date: string;
  weekNumber: number;
  weekStart?: string;
  weekEnd?: string;
  position: number;
  cashIn: number;
  cashOut: number;
  confidence: string;
}

interface ForecastChartProps {
  chartData: ChartDataPoint[];
  scenarioChartData?: ScenarioDataPoint[] | null;
  bufferThreshold: number;
  activeLayers: Set<LayerToggle>;
  toggleLayer: (layer: LayerToggle) => void;
  timeRange: TimeRange;
  changeTimeRange: (range: TimeRange) => void;
  isLoading: boolean;
  isScenarioLoading?: boolean;
  appliedScenarios?: AppliedScenario[];
  savedScenarios?: ScenarioItem[];
  suggestedScenarios?: ScenarioItem[];
  teamScenarios?: ScenarioItem[];
  onScenarioApply?: (scenario: AppliedScenario) => void;
  onScenarioRemove?: (scenarioId: string) => void;
}

// Danger point for buffer warning markers
interface DangerPoint {
  id: string;
  weekIndex: number;
  cashAmount: number;
  date: string;
  shortfall: number;
  isBelowBuffer: boolean;
}

// Danger Signal Marker Component
function DangerSignalMarker({
  point,
  bufferThreshold,
  weeksCount,
  isAcknowledged,
  isSnoozed,
  onCreateAlert,
  onAcknowledge,
  onSnooze,
}: {
  point: DangerPoint;
  bufferThreshold: number;
  weeksCount: number;
  isAcknowledged: boolean;
  isSnoozed: boolean;
  onCreateAlert: (point: DangerPoint) => void;
  onAcknowledge: (pointId: string) => void;
  onSnooze: (pointId: string) => void;
}) {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);

  // Don't render if snoozed
  if (isSnoozed) return null;

  // Position calculation (similar to InsightsOverlay pattern)
  const leftPercent = ((point.weekIndex + 0.5) / weeksCount) * 100;

  // Color based on severity
  const isCritical = point.isBelowBuffer;
  const markerColor = isCritical ? 'bg-tomato' : 'bg-amber-500';
  const markerGlow = isCritical ? 'shadow-tomato/30' : 'shadow-amber-500/30';

  const tooltipMessage = point.isBelowBuffer
    ? `Cash drops to ${formatCurrency(point.cashAmount)} on ${point.date} — ${formatCurrency(Math.abs(point.shortfall))} below your ${formatCurrency(bufferThreshold)} buffer`
    : `Cash approaches ${formatCurrency(point.cashAmount)} on ${point.date} — within 10% of your ${formatCurrency(bufferThreshold)} buffer`;

  return (
    <div
      className="absolute z-20"
      style={{
        left: `${leftPercent}%`,
        top: '55%',
        transform: 'translate(-50%, -100%)',
      }}
    >
      <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
        <RadixTooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <button
                className={cn(
                  'w-7 h-7 rounded-full flex items-center justify-center text-white shadow-lg transition-all hover:scale-110 cursor-pointer',
                  markerColor,
                  markerGlow,
                  isAcknowledged && 'opacity-40',
                  !isAcknowledged && 'animate-pulse'
                )}
                aria-label="Danger warning marker"
              >
                <AlertTriangle className="w-4 h-4" />
              </button>
            </PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs text-xs">
            {tooltipMessage}
          </TooltipContent>
        </RadixTooltip>

        <PopoverContent align="center" className="w-56 p-2">
          <div className="space-y-1">
            <button
              onClick={() => {
                onCreateAlert(point);
                setIsPopoverOpen(false);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gunmetal/5 text-left transition-colors"
            >
              <Bell className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Create Alert</span>
            </button>
            <button
              onClick={() => {
                onAcknowledge(point.id);
                setIsPopoverOpen(false);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gunmetal/5 text-left transition-colors"
            >
              <CheckCircle2 className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Acknowledge</span>
            </button>
            <button
              onClick={() => {
                onSnooze(point.id);
                setIsPopoverOpen(false);
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gunmetal/5 text-left transition-colors"
            >
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Snooze 1 week</span>
            </button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatYAxis = (value: number): string => {
  if (Math.abs(value) >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1000) {
    return `$${Math.round(value / 1000)}K`;
  }
  return `$${value}`;
};

// Team members for tagging
const teamMembers = [
  { id: '1', name: 'Sarah Chen', initials: 'SC', color: '#7C3AED', avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=face' },
  { id: '2', name: 'Marcus Johnson', initials: 'MJ', color: '#059669', avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=face' },
  { id: '3', name: 'Amy Kim', initials: 'AK', color: '#F97316', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face' },
  { id: '4', name: 'John Doe', initials: 'JD', color: '#22C55E', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' },
  { id: '5', name: 'Tom Smith', initials: 'TS', color: '#A855F7', avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=face' },
];

// Comment type with replies
interface Comment {
  id: string;
  weekIndex: number;
  author: { name: string; initials: string; color: string; avatar?: string };
  text: string;
  timestamp: string;
  position: 'top' | 'bottom';
  resolved?: boolean;
  replies?: { author: { name: string; initials: string; color: string; avatar?: string }; text: string; timestamp: string }[];
}

// Mock comments data with replies
const initialComments: Comment[] = [
  {
    id: '1',
    weekIndex: 2,
    author: { name: 'Sarah Chen', initials: 'SC', color: '#7C3AED', avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=face' },
    text: 'This dip is expected - Q1 tax payments hit here',
    timestamp: '2 hours ago',
    position: 'top',
    replies: [
      { author: { name: 'John Doe', initials: 'JD', color: '#22C55E', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' }, text: 'Thanks for the heads up!', timestamp: '1 hour ago' }
    ]
  },
  {
    id: '2',
    weekIndex: 4,
    author: { name: 'Marcus Johnson', initials: 'MJ', color: '#059669', avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=face' },
    text: 'Client payment of $180K confirmed for this week',
    timestamp: 'Yesterday',
    position: 'top',
    resolved: true,
  },
  {
    id: '3',
    weekIndex: 7,
    author: { name: 'Amy Kim', initials: 'AK', color: '#F97316', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=face' },
    text: 'Need to discuss - runway getting tight here',
    timestamp: '3 days ago',
    position: 'bottom',
  },
  {
    id: '4',
    weekIndex: 10,
    author: { name: 'John Doe', initials: 'JD', color: '#22C55E', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face' },
    text: 'Board meeting scheduled - will review projections',
    timestamp: '1 week ago',
    position: 'top',
  },
];

// Comments overlay component with full functionality
function CommentsOverlay({ weeksCount, onAddComment }: { weeksCount: number; onAddComment: (weekIndex: number) => void }) {
  const [hoveredComment, setHoveredComment] = useState<string | null>(null);
  const [pinnedComment, setPinnedComment] = useState<string | null>(null);
  const [comments, setComments] = useState<Comment[]>(initialComments);
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [replyText, setReplyText] = useState('');
  const [showTagMenu, setShowTagMenu] = useState(false);
  const [shareToAll, setShareToAll] = useState(false);
  const replyInputRef = useRef<HTMLInputElement>(null);

  const handleResolve = (commentId: string) => {
    setComments(prev => prev.map(c =>
      c.id === commentId ? { ...c, resolved: !c.resolved } : c
    ));
    const comment = comments.find(c => c.id === commentId);
    toast.success(comment?.resolved ? 'Comment reopened' : 'Comment marked as resolved');
  };

  const handleSendReply = (commentId: string) => {
    if (!replyText.trim()) return;

    const newReply = {
      author: { name: 'You', initials: 'ME', color: '#6366F1' },
      text: replyText,
      timestamp: 'Just now'
    };

    setComments(prev => prev.map(c =>
      c.id === commentId
        ? { ...c, replies: [...(c.replies || []), newReply] }
        : c
    ));

    if (shareToAll) {
      toast.success('Reply shared with all team members');
    } else {
      toast.success('Reply sent');
    }

    setReplyText('');
    setReplyingTo(null);
    setShowTagMenu(false);
    setShareToAll(false);
  };

  const handleTagPerson = (person: typeof teamMembers[0]) => {
    setReplyText(prev => `${prev}@${person.name} `);
    setShowTagMenu(false);
    replyInputRef.current?.focus();
  };

  const isExpanded = (commentId: string) => hoveredComment === commentId || pinnedComment === commentId || replyingTo === commentId;

  return (
    <div className="absolute inset-0 pointer-events-none z-20" style={{ left: 50, right: 70, top: 10, bottom: 30 }}>
      {comments.map((comment) => {
        if (comment.weekIndex >= weeksCount) return null;

        const leftPercent = ((comment.weekIndex + 0.5) / weeksCount) * 100;
        const expanded = isExpanded(comment.id);

        return (
          <div
            key={comment.id}
            className="absolute pointer-events-auto"
            style={{
              left: `${leftPercent}%`,
              top: comment.position === 'top' ? '12%' : '75%',
              transform: 'translateX(-50%)',
            }}
            onMouseEnter={() => setHoveredComment(comment.id)}
            onMouseLeave={() => {
              if (pinnedComment !== comment.id && replyingTo !== comment.id) {
                setHoveredComment(null);
              }
            }}
          >
            {/* Comment marker */}
            <div
              className="relative cursor-pointer group"
              onClick={() => setPinnedComment(pinnedComment === comment.id ? null : comment.id)}
            >
              {/* Avatar bubble */}
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-semibold shadow-lg transition-all overflow-hidden',
                  'ring-2 ring-white hover:scale-110',
                  expanded && 'scale-110',
                  comment.resolved && 'opacity-60'
                )}
                style={{ backgroundColor: comment.author.color }}
              >
                {comment.resolved ? (
                  <Check className="w-4 h-4" />
                ) : comment.author.avatar ? (
                  <img src={comment.author.avatar} alt={comment.author.name} className="w-full h-full object-cover" />
                ) : (
                  comment.author.initials
                )}
              </div>

              {/* Message indicator */}
              {!comment.resolved && (
                <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-white rounded-full flex items-center justify-center shadow-sm">
                  <MessageCircle className="w-2.5 h-2.5 text-gunmetal" />
                </div>
              )}

              {/* Reply count badge */}
              {comment.replies && comment.replies.length > 0 && (
                <div className="absolute -top-1 -right-1 w-4 h-4 bg-gunmetal rounded-full flex items-center justify-center shadow-sm">
                  <span className="text-[9px] text-white font-medium">{comment.replies.length}</span>
                </div>
              )}

              {/* Expanded comment card - shows on hover */}
              {expanded && (
                <div
                  className={cn(
                    'absolute left-1/2 -translate-x-1/2 w-72 glass-strong rounded-xl p-3 shadow-xl border border-white/30',
                    'animate-in fade-in-0 zoom-in-95 duration-200',
                    comment.position === 'top' ? 'top-full mt-2' : 'bottom-full mb-2'
                  )}
                  onClick={(e) => e.stopPropagation()}
                >
                  {/* Arrow */}
                  <div
                    className={cn(
                      'absolute left-1/2 -translate-x-1/2 w-3 h-3 bg-white/80 rotate-45 border-white/30',
                      comment.position === 'top'
                        ? '-top-1.5 border-l border-t'
                        : '-bottom-1.5 border-r border-b'
                    )}
                  />

                  {/* Header */}
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-semibold overflow-hidden"
                      style={{ backgroundColor: comment.author.color }}
                    >
                      {comment.author.avatar ? (
                        <img src={comment.author.avatar} alt={comment.author.name} className="w-full h-full object-cover" />
                      ) : (
                        comment.author.initials
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-gunmetal truncate">
                        {comment.author.name}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {comment.timestamp}
                      </div>
                    </div>
                    {/* Resolve/Approve button */}
                    <button
                      onClick={() => handleResolve(comment.id)}
                      className={cn(
                        'w-6 h-6 rounded-full flex items-center justify-center transition-colors',
                        comment.resolved
                          ? 'bg-lime-dark text-white'
                          : 'bg-white/50 text-muted-foreground hover:bg-lime-dark hover:text-white'
                      )}
                      title={comment.resolved ? 'Reopen' : 'Approve / Resolve'}
                    >
                      <Check className="w-3 h-3" />
                    </button>
                  </div>

                  {/* Comment text */}
                  <p className={cn(
                    'text-xs text-gunmetal leading-relaxed',
                    comment.resolved && 'line-through opacity-60'
                  )}>
                    {comment.text}
                  </p>

                  {/* Existing replies */}
                  {comment.replies && comment.replies.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/30 space-y-2 max-h-24 overflow-y-auto">
                      {comment.replies.map((reply, idx) => (
                        <div key={idx} className="flex gap-2">
                          <div
                            className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[8px] font-semibold flex-shrink-0 overflow-hidden"
                            style={{ backgroundColor: reply.author.color }}
                          >
                            {reply.author.avatar ? (
                              <img src={reply.author.avatar} alt={reply.author.name} className="w-full h-full object-cover" />
                            ) : (
                              reply.author.initials
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1">
                              <span className="text-[10px] font-medium text-gunmetal">{reply.author.name}</span>
                              <span className="text-[9px] text-muted-foreground">{reply.timestamp}</span>
                            </div>
                            <p className="text-[11px] text-gunmetal/80">{reply.text}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Reply section */}
                  {replyingTo === comment.id ? (
                    <div className="mt-3 pt-2 border-t border-border/30">
                      {/* Tag menu */}
                      {showTagMenu && (
                        <div className="mb-2 p-2 bg-white/80 rounded-lg border border-white/30 max-h-28 overflow-y-auto">
                          <div className="text-[10px] text-muted-foreground mb-1.5">Tag someone:</div>
                          {teamMembers.map((person) => (
                            <button
                              key={person.id}
                              onClick={() => handleTagPerson(person)}
                              className="w-full flex items-center gap-2 p-1.5 rounded hover:bg-white/50 transition-colors"
                            >
                              <div
                                className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[8px] font-semibold overflow-hidden"
                                style={{ backgroundColor: person.color }}
                              >
                                {person.avatar ? (
                                  <img src={person.avatar} alt={person.name} className="w-full h-full object-cover" />
                                ) : (
                                  person.initials
                                )}
                              </div>
                              <span className="text-[11px] text-gunmetal">{person.name}</span>
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Reply input */}
                      <div className="flex items-center gap-1.5">
                        <div className="flex-1 relative">
                          <input
                            ref={replyInputRef}
                            type="text"
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSendReply(comment.id);
                              }
                              if (e.key === '@') {
                                setShowTagMenu(true);
                              }
                            }}
                            placeholder="Reply... (@ to tag)"
                            className="w-full px-2.5 py-1.5 text-[11px] bg-white/50 border border-white/30 rounded-lg focus:outline-none focus:ring-1 focus:ring-gunmetal/20"
                            autoFocus
                          />
                        </div>
                        <button
                          onClick={() => setShowTagMenu(!showTagMenu)}
                          className={cn(
                            'w-7 h-7 rounded-lg flex items-center justify-center transition-colors',
                            showTagMenu ? 'bg-gunmetal text-white' : 'bg-white/50 text-muted-foreground hover:bg-white/80'
                          )}
                          title="Tag someone"
                        >
                          <AtSign className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setShareToAll(!shareToAll)}
                          className={cn(
                            'w-7 h-7 rounded-lg flex items-center justify-center transition-colors',
                            shareToAll ? 'bg-gunmetal text-white' : 'bg-white/50 text-muted-foreground hover:bg-white/80'
                          )}
                          title="Share to all"
                        >
                          <Users className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleSendReply(comment.id)}
                          disabled={!replyText.trim()}
                          className="w-7 h-7 rounded-lg bg-gunmetal text-white flex items-center justify-center hover:bg-gunmetal/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          <Send className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {/* Share indicator */}
                      {shareToAll && (
                        <div className="mt-1.5 text-[9px] text-muted-foreground flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          Will notify all team members
                        </div>
                      )}

                      {/* Cancel button */}
                      <button
                        onClick={() => {
                          setReplyingTo(null);
                          setReplyText('');
                          setShowTagMenu(false);
                          setShareToAll(false);
                        }}
                        className="mt-2 text-[10px] text-muted-foreground hover:text-gunmetal transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setReplyingTo(comment.id)}
                      className="mt-2 text-[10px] text-muted-foreground hover:text-gunmetal transition-colors"
                    >
                      Reply...
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Connecting line to data point */}
            <div
              className={cn(
                'absolute left-1/2 -translate-x-1/2 w-px opacity-40',
                comment.position === 'top'
                  ? 'top-full h-12'
                  : 'bottom-full h-12'
              )}
              style={{
                background: `linear-gradient(${comment.position === 'top' ? 'to bottom' : 'to top'}, ${comment.author.color}, transparent)`
              }}
            />
          </div>
        );
      })}

      {/* Add comment button - floating */}
      <div className="absolute bottom-4 right-4 pointer-events-auto">
        <button
          onClick={() => onAddComment(Math.floor(weeksCount / 2))}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gunmetal text-white rounded-lg text-xs font-medium shadow-lg hover:bg-gunmetal/90 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Comment
        </button>
      </div>
    </div>
  );
}

// Add comment modal
function AddCommentModal({
  weekIndex,
  weeksCount,
  onClose,
  onSubmit
}: {
  weekIndex: number;
  weeksCount: number;
  onClose: () => void;
  onSubmit: (text: string, weekIndex: number, shareToAll: boolean) => void;
}) {
  const [text, setText] = useState('');
  const [selectedWeek, setSelectedWeek] = useState(weekIndex);
  const [shareToAll, setShareToAll] = useState(false);
  const [showTagMenu, setShowTagMenu] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleTagPerson = (person: typeof teamMembers[0]) => {
    setText(prev => `${prev}@${person.name} `);
    setShowTagMenu(false);
    inputRef.current?.focus();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
      <div className="glass-strong rounded-xl p-4 w-80 shadow-2xl border border-white/30 animate-in fade-in-0 zoom-in-95 duration-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gunmetal">Add Comment</h3>
          <button
            onClick={onClose}
            className="w-6 h-6 rounded-full hover:bg-gunmetal/10 flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Week selector */}
        <div className="mb-3">
          <label className="text-[10px] text-muted-foreground mb-1 block">Position on chart</label>
          <select
            value={selectedWeek}
            onChange={(e) => setSelectedWeek(Number(e.target.value))}
            className="w-full px-2.5 py-1.5 text-xs bg-white/50 border border-white/30 rounded-lg focus:outline-none focus:ring-1 focus:ring-gunmetal/20"
          >
            {Array.from({ length: weeksCount }, (_, i) => (
              <option key={i} value={i}>Week {i}</option>
            ))}
          </select>
        </div>

        {/* Tag menu */}
        {showTagMenu && (
          <div className="mb-2 p-2 bg-white/80 rounded-lg border border-white/30 max-h-32 overflow-y-auto">
            <div className="text-[10px] text-muted-foreground mb-1.5">Tag someone:</div>
            {teamMembers.map((person) => (
              <button
                key={person.id}
                onClick={() => handleTagPerson(person)}
                className="w-full flex items-center gap-2 p-1.5 rounded hover:bg-white/50 transition-colors"
              >
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[8px] font-semibold overflow-hidden"
                  style={{ backgroundColor: person.color }}
                >
                  {person.avatar ? (
                    <img src={person.avatar} alt={person.name} className="w-full h-full object-cover" />
                  ) : (
                    person.initials
                  )}
                </div>
                <span className="text-[11px] text-gunmetal">{person.name}</span>
              </button>
            ))}
          </div>
        )}

        {/* Comment input */}
        <textarea
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === '@') {
              setShowTagMenu(true);
            }
          }}
          placeholder="Write your comment... (use @ to tag)"
          className="w-full px-2.5 py-2 text-xs bg-white/50 border border-white/30 rounded-lg focus:outline-none focus:ring-1 focus:ring-gunmetal/20 resize-none h-20"
          autoFocus
        />

        {/* Action buttons */}
        <div className="flex items-center gap-2 mt-3">
          <button
            onClick={() => setShowTagMenu(!showTagMenu)}
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
              showTagMenu ? 'bg-gunmetal text-white' : 'bg-white/50 text-muted-foreground hover:bg-white/80'
            )}
            title="Tag someone"
          >
            <AtSign className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShareToAll(!shareToAll)}
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
              shareToAll ? 'bg-gunmetal text-white' : 'bg-white/50 text-muted-foreground hover:bg-white/80'
            )}
            title="Share to all team members"
          >
            <Users className="w-4 h-4" />
          </button>
          <div className="flex-1" />
          <Button
            variant="outline"
            size="sm"
            onClick={onClose}
            className="text-xs"
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => {
              if (text.trim()) {
                onSubmit(text, selectedWeek, shareToAll);
              }
            }}
            disabled={!text.trim()}
            className="text-xs gap-1"
          >
            <Send className="w-3 h-3" />
            Post
          </Button>
        </div>

        {shareToAll && (
          <div className="mt-2 text-[9px] text-muted-foreground flex items-center gap-1">
            <Users className="w-3 h-3" />
            Will notify all team members
          </div>
        )}
      </div>
    </div>
  );
}

// Generate insights based on chart data
function generateInsights(chartData: ChartDataPoint[], bufferThreshold: number) {
  if (!chartData.length) return [];

  const insights: Array<{
    id: string;
    weekIndex: number;
    type: 'warning' | 'opportunity' | 'trend' | 'action';
    title: string;
    description: string;
    dataPoint: string;
    icon: typeof Sparkles;
    color: string;
    position: 'top' | 'bottom';
  }> = [];

  // Find significant data points
  const minPoint = chartData.reduce((min, d, i) =>
    d.position < min.value ? { value: d.position, index: i, data: d } : min,
    { value: Infinity, index: 0, data: chartData[0] }
  );

  const maxPoint = chartData.reduce((max, d, i) =>
    d.position > max.value ? { value: d.position, index: i, data: d } : max,
    { value: -Infinity, index: 0, data: chartData[0] }
  );

  // Find where cash approaches buffer
  const bufferApproachIndex = chartData.findIndex(d => d.position < bufferThreshold * 1.3);

  // Find biggest single-week drop
  let maxDrop = { value: 0, index: 0 };
  for (let i = 1; i < chartData.length; i++) {
    const drop = chartData[i - 1].position - chartData[i].position;
    if (drop > maxDrop.value) {
      maxDrop = { value: drop, index: i };
    }
  }

  // Find biggest recovery
  let maxRecovery = { value: 0, index: 0 };
  for (let i = 1; i < chartData.length; i++) {
    const recovery = chartData[i].position - chartData[i - 1].position;
    if (recovery > maxRecovery.value) {
      maxRecovery = { value: recovery, index: i };
    }
  }

  // Add insight for minimum cash point
  if (minPoint.index > 0 && minPoint.value < bufferThreshold * 2) {
    insights.push({
      id: 'min-cash',
      weekIndex: minPoint.index,
      type: 'warning',
      title: 'Cash Low Point',
      description: `Cash position reaches its lowest at ${formatCurrency(minPoint.value)}. Consider delaying non-essential expenses or accelerating receivables before this week.`,
      dataPoint: formatCurrency(minPoint.value),
      icon: ShieldAlert,
      color: '#FF4F3F',
      position: 'bottom',
    });
  }

  // Add insight for buffer approach
  if (bufferApproachIndex > 0 && bufferApproachIndex !== minPoint.index) {
    insights.push({
      id: 'buffer-approach',
      weekIndex: bufferApproachIndex,
      type: 'warning',
      title: 'Approaching Buffer',
      description: `Cash is approaching your ${formatCurrency(bufferThreshold)} safety buffer. Monitor closely and review upcoming commitments.`,
      dataPoint: formatCurrency(chartData[bufferApproachIndex].position),
      icon: ShieldAlert,
      color: '#F59E0B',
      position: 'top',
    });
  }

  // Add insight for max cash point (opportunity)
  if (maxPoint.index > 0 && maxPoint.index < chartData.length - 1) {
    insights.push({
      id: 'peak-cash',
      weekIndex: maxPoint.index,
      type: 'opportunity',
      title: 'Peak Cash Position',
      description: `Optimal time for strategic investments or early vendor payments. Cash peaks at ${formatCurrency(maxPoint.value)}.`,
      dataPoint: formatCurrency(maxPoint.value),
      icon: Sparkles,
      color: '#7CB518',
      position: 'top',
    });
  }

  // Add insight for significant drop
  if (maxDrop.value > 100000 && maxDrop.index !== minPoint.index) {
    insights.push({
      id: 'big-drop',
      weekIndex: maxDrop.index,
      type: 'action',
      title: 'Large Outflow Week',
      description: `${formatCurrency(maxDrop.value)} outflow expected. Review scheduled payments and consider spreading across multiple weeks if possible.`,
      dataPoint: `-${formatCurrency(maxDrop.value)}`,
      icon: Zap,
      color: '#DC2626',
      position: 'bottom',
    });
  }

  // Add insight for recovery
  if (maxRecovery.value > 150000) {
    insights.push({
      id: 'recovery',
      weekIndex: maxRecovery.index,
      type: 'trend',
      title: 'Strong Inflow Expected',
      description: `${formatCurrency(maxRecovery.value)} recovery projected. Ensure receivables are tracked and follow up on any pending invoices.`,
      dataPoint: `+${formatCurrency(maxRecovery.value)}`,
      icon: Lightbulb,
      color: '#059669',
      position: 'top',
    });
  }

  return insights;
}

// Insights overlay component - TAMI AI suggestions
function InsightsOverlay({
  chartData,
  bufferThreshold,
  weeksCount
}: {
  chartData: ChartDataPoint[];
  bufferThreshold: number;
  weeksCount: number;
}) {
  const [expandedInsight, setExpandedInsight] = useState<string | null>(null);
  const insights = useMemo(() => generateInsights(chartData, bufferThreshold), [chartData, bufferThreshold]);

  return (
    <div className="absolute inset-0 pointer-events-none z-20" style={{ left: 50, right: 70, top: 10, bottom: 30 }}>
      {insights.map((insight) => {
        if (insight.weekIndex >= weeksCount) return null;

        const leftPercent = ((insight.weekIndex + 0.5) / weeksCount) * 100;
        const isExpanded = expandedInsight === insight.id;
        const Icon = insight.icon;

        return (
          <div
            key={insight.id}
            className="absolute pointer-events-auto"
            style={{
              left: `${leftPercent}%`,
              top: insight.position === 'top' ? '8%' : '78%',
              transform: 'translateX(-50%)',
            }}
          >
            {/* Insight marker */}
            <div
              className="relative cursor-pointer group"
              onClick={() => setExpandedInsight(isExpanded ? null : insight.id)}
            >
              {/* Icon bubble with pulse animation */}
              <div
                className={cn(
                  'w-9 h-9 rounded-xl flex items-center justify-center text-white shadow-lg transition-all',
                  'ring-2 ring-white hover:scale-110',
                  isExpanded && 'scale-110'
                )}
                style={{ backgroundColor: insight.color }}
              >
                <Icon className="w-4.5 h-4.5" />
                {/* Pulse ring */}
                <span
                  className="absolute inset-0 rounded-xl animate-ping opacity-30"
                  style={{ backgroundColor: insight.color }}
                />
              </div>

              {/* TAMI badge */}
              <div className="absolute -bottom-1 -right-1 px-1 py-0.5 bg-gunmetal rounded text-[8px] font-bold text-white shadow-sm">
                TAMI
              </div>

              {/* Expanded insight card */}
              {isExpanded && (
                <div
                  className={cn(
                    'absolute left-1/2 -translate-x-1/2 w-72 glass-strong rounded-xl p-4 shadow-xl border border-white/30',
                    'animate-in fade-in-0 zoom-in-95 duration-200',
                    insight.position === 'top' ? 'top-full mt-3' : 'bottom-full mb-3'
                  )}
                >
                  {/* Arrow */}
                  <div
                    className={cn(
                      'absolute left-1/2 -translate-x-1/2 w-3 h-3 bg-white/80 rotate-45 border-white/30',
                      insight.position === 'top'
                        ? '-top-1.5 border-l border-t'
                        : '-bottom-1.5 border-r border-b'
                    )}
                  />

                  {/* Header */}
                  <div className="flex items-start gap-3 mb-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-white shrink-0"
                      style={{ backgroundColor: insight.color }}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-gunmetal">
                          {insight.title}
                        </span>
                        <span
                          className="px-1.5 py-0.5 rounded text-[9px] font-medium text-white"
                          style={{ backgroundColor: insight.color }}
                        >
                          {insight.type}
                        </span>
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        Week {insight.weekIndex} • {insight.dataPoint}
                      </div>
                    </div>
                  </div>

                  {/* Insight description */}
                  <p className="text-xs text-gunmetal leading-relaxed mb-3">
                    {insight.description}
                  </p>

                  {/* Action buttons */}
                  <div className="flex gap-2">
                    <button
                      className="flex-1 py-1.5 px-2.5 bg-gunmetal text-white rounded-md text-[11px] font-medium cursor-pointer transition-all hover:bg-gunmetal/90 flex items-center justify-center gap-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        toast.info('Opening TAMI chat to discuss this insight...');
                      }}
                    >
                      <MessageCircle className="w-3 h-3" />
                      Ask TAMI
                    </button>
                    <button
                      className="py-1.5 px-2.5 bg-white/50 border border-white/30 rounded-md text-muted-foreground text-[11px] cursor-pointer transition-all hover:bg-white/70"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedInsight(null);
                      }}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Connecting line to data point */}
            <div
              className={cn(
                'absolute left-1/2 -translate-x-1/2 w-px',
                insight.position === 'top'
                  ? 'top-full h-16'
                  : 'bottom-full h-16'
              )}
              style={{
                background: `linear-gradient(${insight.position === 'top' ? 'to bottom' : 'to top'}, ${insight.color}, transparent)`
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

// Custom tooltip for data points - Enhanced version
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload as ChartDataPoint;

  // Format week date range or fallback to date
  const dateDisplay = data.weekStart && data.weekEnd
    ? `${data.weekStart}-${data.weekEnd}`
    : data.date;

  return (
    <div className="glass-strong rounded-xl p-4 min-w-[220px] shadow-xl border border-white/30 animate-in fade-in-0 zoom-in-95 duration-150">
      {/* Header: Week number and date range */}
      <div className="text-sm font-semibold text-gunmetal mb-1">
        Week {data.weekNumber} · {dateDisplay}
      </div>

      {/* Separator */}
      <div className="h-px bg-border/50 my-2.5" />

      {/* Metrics rows */}
      <div className="space-y-2">
        <div className="flex justify-between items-center text-xs">
          <span className="text-muted-foreground">Position</span>
          <span className="font-semibold text-gunmetal tabular-nums">
            {formatCurrency(data.position)}
          </span>
        </div>
        <div className="flex justify-between items-center text-xs">
          <span className="text-muted-foreground">Cash In</span>
          <span className="font-medium text-lime-dark tabular-nums">
            +{formatCurrency(data.cashIn)}
          </span>
        </div>
        <div className="flex justify-between items-center text-xs">
          <span className="text-muted-foreground">Cash Out</span>
          <span className="font-medium text-tomato tabular-nums">
            -{formatCurrency(data.cashOut)}
          </span>
        </div>
      </div>

      {/* Separator */}
      <div className="h-px bg-border/50 my-2.5" />

      {/* Action button */}
      <button
        className="w-full py-2 px-3 bg-gunmetal/5 hover:bg-gunmetal hover:text-white rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-1.5"
        onClick={() => toast.info('Transaction view coming soon')}
      >
        View transactions
        <ArrowRight className="w-3 h-3" />
      </button>
    </div>
  );
}

// Projections Data Popup for drill-down
function ProjectionsDataPopup({
  data,
  lineType,
  onClose
}: {
  data: ChartDataPoint;
  lineType: 'bestCase' | 'expected' | 'worstCase';
  onClose: () => void;
}) {
  const lineConfig = {
    bestCase: { label: 'Best Case', color: 'text-lime-dark', bgColor: 'bg-lime/10', borderColor: 'border-lime-dark' },
    expected: { label: 'Expected', color: 'text-gunmetal', bgColor: 'bg-gunmetal/10', borderColor: 'border-gunmetal' },
    worstCase: { label: 'Worst Case', color: 'text-tomato', bgColor: 'bg-tomato/10', borderColor: 'border-tomato' },
  };

  const config = lineConfig[lineType];
  const value = lineType === 'bestCase' ? data.bestCase : lineType === 'worstCase' ? data.worstCase : data.position;

  return (
    <div className="glass-strong rounded-xl p-4 min-w-[280px] shadow-xl border border-white/30">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-border/50">
        <div className="flex items-center gap-2">
          <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-semibold', config.bgColor, config.color)}>
            {config.label}
          </span>
          <span className="text-xs text-muted-foreground">{data.date}</span>
        </div>
        <button
          onClick={onClose}
          className="w-5 h-5 rounded-full hover:bg-gunmetal/10 flex items-center justify-center transition-colors"
        >
          <X className="w-3 h-3 text-muted-foreground" />
        </button>
      </div>

      {/* Main Value */}
      <div className="mb-4">
        <div className="text-[11px] text-muted-foreground mb-1">Projected Cash Position</div>
        <div className={cn('text-2xl font-bold', config.color)}>{formatCurrency(value)}</div>
      </div>

      {/* Breakdown */}
      <div className="space-y-2 mb-4">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-lime-dark" />
            <span className="text-muted-foreground">Expected Inflows</span>
          </div>
          <span className="font-medium text-lime-dark">+{formatCurrency(data.cashIn)}</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-3.5 h-3.5 text-tomato" />
            <span className="text-muted-foreground">Expected Outflows</span>
          </div>
          <span className="font-medium text-tomato">-{formatCurrency(data.cashOut)}</span>
        </div>
        <div className="flex items-center justify-between text-xs pt-2 border-t border-border/30">
          <div className="flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5 text-gunmetal" />
            <span className="text-muted-foreground">Net Change</span>
          </div>
          <span className={cn('font-medium', data.cashIn - data.cashOut >= 0 ? 'text-lime-dark' : 'text-tomato')}>
            {data.cashIn - data.cashOut >= 0 ? '+' : ''}{formatCurrency(data.cashIn - data.cashOut)}
          </span>
        </div>
      </div>

      {/* Confidence Indicator */}
      <div className="flex items-center gap-2 mb-4 p-2 rounded-lg bg-white/50">
        <Calendar className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-[11px] text-muted-foreground">
          Confidence: <span className={cn('font-medium',
            data.confidence === 'high' ? 'text-lime-dark' :
            data.confidence === 'medium' ? 'text-amber-600' : 'text-tomato'
          )}>{data.confidence}</span>
        </span>
      </div>

      {/* Action Button */}
      <Button
        variant="outline"
        size="sm"
        className="w-full text-xs gap-1.5"
        onClick={() => toast.info('Detailed projections view coming soon')}
      >
        View Full Breakdown
        <ArrowRight className="w-3 h-3" />
      </Button>
    </div>
  );
}

// Legend component for the chart
function ChartLegend() {
  return (
    <div className="absolute top-2 right-2 glass-subtle rounded-md p-2 text-[10px] z-20">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="w-2 h-2 rounded-full bg-lime-dark" />
        <span className="text-muted-foreground">Best case</span>
      </div>
      <div className="flex items-center gap-1.5 mb-1">
        <span className="w-2 h-2 rounded-full bg-gunmetal" />
        <span className="text-muted-foreground">Expected</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-tomato" />
        <span className="text-muted-foreground">Worst case</span>
      </div>
    </div>
  );
}

export function ForecastChart({
  chartData,
  scenarioChartData,
  bufferThreshold,
  activeLayers,
  toggleLayer,
  timeRange,
  changeTimeRange,
  isLoading,
  isScenarioLoading = false,
  appliedScenarios = [],
  savedScenarios,
  suggestedScenarios,
  teamScenarios,
  onScenarioApply,
  onScenarioRemove,
}: ForecastChartProps) {
  // State for projections popup
  const [projectionsPopup, setProjectionsPopup] = useState<{
    data: ChartDataPoint;
    lineType: 'bestCase' | 'expected' | 'worstCase';
    position: { x: number; y: number };
  } | null>(null);

  // State for add comment modal
  const [addCommentModal, setAddCommentModal] = useState<{ weekIndex: number } | null>(null);

  // State for danger signal markers
  const [acknowledgedPoints, setAcknowledgedPoints] = useState<Set<string>>(new Set());
  const [snoozedPoints, setSnoozedPoints] = useState<Set<string>>(new Set());

  // Handle add comment
  const handleAddComment = (weekIndex: number) => {
    setAddCommentModal({ weekIndex });
  };

  // Handle submit comment
  const handleSubmitComment = (text: string, _weekIndex: number, shareToAll: boolean) => {
    toast.success(shareToAll ? 'Comment posted and shared with team' : 'Comment posted');
    setAddCommentModal(null);
  };

  // Calculate danger points for danger signal markers
  const dangerPoints = useMemo((): DangerPoint[] => {
    return chartData
      .map((d, index) => ({
        id: `danger-${index}-${d.weekNumber}`,
        weekIndex: index,
        cashAmount: d.position,
        date: d.date,
        shortfall: bufferThreshold - d.position,
        isBelowBuffer: d.position < bufferThreshold,
      }))
      .filter(p => p.cashAmount < bufferThreshold * 1.1); // Within 10% of buffer or below
  }, [chartData, bufferThreshold]);

  // Handlers for danger signal markers
  const handleCreateAlert = useCallback((point: DangerPoint) => {
    toast.success(`Alert created for ${point.date} - Cash position: ${formatCurrency(point.cashAmount)}`);
  }, []);

  const handleAcknowledgePoint = useCallback((pointId: string) => {
    setAcknowledgedPoints(prev => new Set([...prev, pointId]));
    toast.info('Warning acknowledged');
  }, []);

  const handleSnoozePoint = useCallback((pointId: string) => {
    setSnoozedPoints(prev => new Set([...prev, pointId]));
    toast.info('Warning snoozed for 1 week');
  }, []);

  // Calculate Y axis domain including best/worst case
  const yDomain = useMemo(() => {
    if (!chartData.length) return [0, 500000];
    const allValues = chartData.flatMap((d) => [d.position, d.bestCase, d.worstCase]);
    const max = Math.max(...allValues, bufferThreshold * 1.5);
    const min = Math.min(...allValues, 0);
    return [Math.floor(min / 50000) * 50000, Math.ceil(max / 50000) * 50000];
  }, [chartData, bufferThreshold]);

  // Handle line point click
  const handleLineClick = (lineType: 'bestCase' | 'expected' | 'worstCase') => (data: ChartDataPoint, _index: number, event: React.MouseEvent) => {
    setProjectionsPopup({
      data,
      lineType,
      position: { x: event.clientX, y: event.clientY },
    });
  };

  if (isLoading && !chartData.length) {
    return (
      <NeuroCard className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center px-4 py-2 border-b border-white/20">
          <Skeleton className="h-8 w-32" />
          <div className="ml-4 flex gap-2">
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-7 w-20" />
          </div>
        </div>
        <div className="flex-1 p-5">
          <Skeleton className="w-full h-full rounded-xl" />
        </div>
      </NeuroCard>
    );
  }

  return (
    <NeuroCard className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <ChartToolbar
        activeLayers={activeLayers}
        toggleLayer={toggleLayer}
        timeRange={timeRange}
        changeTimeRange={changeTimeRange}
        appliedScenarios={appliedScenarios}
        savedScenarios={savedScenarios}
        suggestedScenarios={suggestedScenarios}
        teamScenarios={teamScenarios}
        onScenarioSelect={onScenarioApply}
        onScenarioRemove={onScenarioRemove}
      />

      {/* Chart Container */}
      <div className="flex-1 p-4 relative">
        <div
          className={cn(
            'bg-white/30 backdrop-blur-sm rounded-xl border border-white/20 h-full relative overflow-hidden',
            isLoading && 'opacity-60'
          )}
        >
          {/* Loading shimmer */}
          {isLoading && (
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse pointer-events-none z-30" />
          )}

          {/* Legend for confidence lines */}
          {activeLayers.has('confidence') && chartData.length > 0 && (
            <ChartLegend />
          )}

          {/* Comments Overlay */}
          {activeLayers.has('comments') && chartData.length > 0 && (
            <CommentsOverlay weeksCount={chartData.length} onAddComment={handleAddComment} />
          )}

          {/* Insights Overlay - TAMI AI suggestions */}
          {activeLayers.has('ai') && chartData.length > 0 && (
            <InsightsOverlay
              chartData={chartData}
              bufferThreshold={bufferThreshold}
              weeksCount={chartData.length}
            />
          )}

          {/* Projections Data Popup */}
          {projectionsPopup && (
            <div
              className="fixed z-50"
              style={{
                left: Math.min(projectionsPopup.position.x, window.innerWidth - 300),
                top: Math.min(projectionsPopup.position.y - 100, window.innerHeight - 400),
              }}
            >
              <ProjectionsDataPopup
                data={projectionsPopup.data}
                lineType={projectionsPopup.lineType}
                onClose={() => setProjectionsPopup(null)}
              />
            </div>
          )}

          {/* Main Chart */}
          <div className="absolute inset-2">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartData}
                margin={{ top: 10, right: 70, bottom: 20, left: 10 }}
              >
                <defs>
                  <linearGradient id="lineGradientLight" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#7CB518" />
                    <stop offset="50%" stopColor="#F59E0B" />
                    <stop offset="100%" stopColor="#FF4F3F" />
                  </linearGradient>
                  <linearGradient id="areaGradientLight" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#112331" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#112331" stopOpacity={0} />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  stroke="rgba(17, 35, 49, 0.25)"
                  strokeDasharray="0"
                  vertical={false}
                  horizontal={true}
                />

                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#4A5B68', fontSize: 10 }}
                  dy={10}
                />

                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#4A5B68', fontSize: 10 }}
                  tickFormatter={formatYAxis}
                  domain={yDomain}
                  dx={-10}
                />

                {/* Buffer Reference Line */}
                <ReferenceLine
                  y={bufferThreshold}
                  stroke="#F59E0B"
                  strokeWidth={2}
                  strokeDasharray="8 4"
                  label={{
                    value: `Buffer ${formatYAxis(bufferThreshold)}`,
                    position: 'right',
                    fill: '#4A5B68',
                    fontSize: 10,
                    fontWeight: 600,
                    offset: 10,
                  }}
                />

                {/* Area fill between best and worst case when confidence is active */}
                {activeLayers.has('confidence') && (
                  <Area
                    type="monotone"
                    dataKey="bestCase"
                    fill="url(#areaGradientLight)"
                    stroke="none"
                    fillOpacity={0.1}
                  />
                )}

                {/* Best Case Line (Green) - only shown when confidence layer is active */}
                {activeLayers.has('confidence') && (
                  <Line
                    type="monotone"
                    dataKey="bestCase"
                    stroke="#7CB518"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    dot={(props: any) => {
                      const { cx, cy, payload, index } = props;
                      return (
                        <circle
                          key={`best-dot-${index}`}
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill="#7CB518"
                          stroke="white"
                          strokeWidth={2}
                          className="cursor-pointer transition-transform hover:scale-150"
                          onClick={(e) => handleLineClick('bestCase')(payload, index, e as unknown as React.MouseEvent)}
                        />
                      );
                    }}
                    activeDot={{
                      r: 6,
                      stroke: '#7CB518',
                      strokeWidth: 2,
                      fill: 'white',
                      cursor: 'pointer',
                    }}
                  />
                )}

                {/* Worst Case Line (Red) - only shown when confidence layer is active */}
                {activeLayers.has('confidence') && (
                  <Line
                    type="monotone"
                    dataKey="worstCase"
                    stroke="#FF4F3F"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                    dot={(props: any) => {
                      const { cx, cy, payload, index } = props;
                      return (
                        <circle
                          key={`worst-dot-${index}`}
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill="#FF4F3F"
                          stroke="white"
                          strokeWidth={2}
                          className="cursor-pointer transition-transform hover:scale-150"
                          onClick={(e) => handleLineClick('worstCase')(payload, index, e as unknown as React.MouseEvent)}
                        />
                      );
                    }}
                    activeDot={{
                      r: 6,
                      stroke: '#FF4F3F',
                      strokeWidth: 2,
                      fill: 'white',
                      cursor: 'pointer',
                    }}
                  />
                )}

                {/* Expected Line (Black/Main) - always shown */}
                <Line
                  type="monotone"
                  dataKey="position"
                  stroke="#112331"
                  strokeWidth={2.5}
                  dot={(props: any) => {
                    const { cx, cy, payload, index } = props;
                    return (
                      <circle
                        key={`expected-dot-${index}`}
                        cx={cx}
                        cy={cy}
                        r={5}
                        fill="#112331"
                        stroke="white"
                        strokeWidth={2}
                        className="cursor-pointer transition-transform hover:scale-150"
                        onClick={(e) => handleLineClick('expected')(payload, index, e as unknown as React.MouseEvent)}
                      />
                    );
                  }}
                  activeDot={{
                    r: 7,
                    stroke: '#112331',
                    strokeWidth: 2,
                    fill: 'white',
                    cursor: 'pointer',
                  }}
                />

                {/* Scenario Line (Lime/Dashed) - shown when scenario is applied */}
                {scenarioChartData && scenarioChartData.length > 0 && (
                  <Line
                    type="monotone"
                    data={scenarioChartData}
                    dataKey="position"
                    stroke="#C5FF35"
                    strokeWidth={2.5}
                    strokeDasharray="8 4"
                    dot={(props: any) => {
                      const { cx, cy, index } = props;
                      return (
                        <circle
                          key={`scenario-dot-${index}`}
                          cx={cx}
                          cy={cy}
                          r={4}
                          fill="#C5FF35"
                          stroke="#112331"
                          strokeWidth={1.5}
                        />
                      );
                    }}
                    activeDot={{
                      r: 6,
                      stroke: '#C5FF35',
                      strokeWidth: 2,
                      fill: '#112331',
                    }}
                    name="Scenario"
                  />
                )}

                <Tooltip
                  content={<CustomTooltip />}
                  cursor={{
                    stroke: '#112331',
                    strokeWidth: 1,
                    strokeDasharray: '4 4',
                  }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Danger Signal Markers */}
          {dangerPoints.length > 0 && chartData.length > 0 && (
            <>
              {dangerPoints.map((point) => (
                <DangerSignalMarker
                  key={point.id}
                  point={point}
                  bufferThreshold={bufferThreshold}
                  weeksCount={chartData.length}
                  isAcknowledged={acknowledgedPoints.has(point.id)}
                  isSnoozed={snoozedPoints.has(point.id)}
                  onCreateAlert={handleCreateAlert}
                  onAcknowledge={handleAcknowledgePoint}
                  onSnooze={handleSnoozePoint}
                />
              ))}
            </>
          )}

          {/* Chart Legend - shown when scenario is active */}
          {scenarioChartData && scenarioChartData.length > 0 && (
            <div className="absolute top-4 right-4 flex items-center gap-4 px-3 py-2 bg-white/80 backdrop-blur-sm rounded-lg border border-white/30 shadow-sm z-20">
              <div className="flex items-center gap-2">
                <div className="w-6 h-0.5 bg-gunmetal rounded" />
                <span className="text-[11px] font-medium text-gunmetal">Base Forecast</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-6 h-0.5 bg-lime rounded" style={{ background: 'repeating-linear-gradient(90deg, #C5FF35 0, #C5FF35 4px, transparent 4px, transparent 6px)' }} />
                <span className="text-[11px] font-medium text-gunmetal">With Scenario</span>
              </div>
            </div>
          )}

          {/* Scenario Loading Indicator */}
          {isScenarioLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 backdrop-blur-sm z-30">
              <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-md">
                <div className="w-4 h-4 border-2 border-lime border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gunmetal">Loading scenario...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Add Comment Modal */}
      {addCommentModal && (
        <AddCommentModal
          weekIndex={addCommentModal.weekIndex}
          weeksCount={chartData.length}
          onClose={() => setAddCommentModal(null)}
          onSubmit={handleSubmitComment}
        />
      )}
    </NeuroCard>
  );
}