import { useState } from 'react';
import {
  Wallet,
  Receipt,
  Users,
  FileText,
  TrendingUp,
  MoreVertical,
  Pencil,
  Copy,
  Trash2,
  History,
  Play,
} from 'lucide-react';
import { NeuroCard, NeuroCardContent } from '@/components/ui/neuro-card';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useRules } from '@/contexts/RulesContext';
import { type Rule, type RuleType, getStatusStyles } from '@/lib/api/rules';
import { toast } from 'sonner';

const RULE_ICONS: Record<RuleType, typeof Wallet> = {
  cash_buffer: Wallet,
  tax_vat_reserve: Receipt,
  payroll: Users,
  receivables: FileText,
  unusual_activity: TrendingUp,
};

interface RuleCardProps {
  rule: Rule;
}

export function RuleCard({ rule }: RuleCardProps) {
  const { toggleRuleStatus, deleteRule, duplicateRule, openEditSheet } = useRules();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const Icon = RULE_ICONS[rule.rule_type];
  const evaluationStatus = rule.current_evaluation?.status || (rule.status === 'paused' ? 'paused' : 'healthy');
  const statusStyles = getStatusStyles(evaluationStatus);

  const handleToggle = () => {
    toggleRuleStatus(rule.id);
    toast.success(rule.status === 'active' ? 'Rule paused' : 'Rule activated');
  };

  const handleDuplicate = () => {
    const duplicated = duplicateRule(rule.id);
    if (duplicated) {
      toast.success('Rule duplicated');
    }
  };

  const handleDelete = () => {
    deleteRule(rule.id);
    toast.success('Rule deleted');
    setIsDeleteDialogOpen(false);
  };

  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  };

  return (
    <>
      <NeuroCard className="hover:shadow-lg transition-shadow">
        <NeuroCardContent className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-white/60 flex items-center justify-center flex-shrink-0">
                <Icon className="h-5 w-5 text-gunmetal" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-league-spartan font-semibold text-gunmetal truncate">
                    {rule.name}
                  </h3>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {rule.description}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-shrink-0">
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusStyles.bgClass} ${statusStyles.textClass}`}>
                <div className={`w-1.5 h-1.5 rounded-full ${statusStyles.dotClass}`} />
                {evaluationStatus === 'healthy' && 'Healthy'}
                {evaluationStatus === 'warning' && 'Warning'}
                {evaluationStatus === 'triggered' && 'Triggered'}
                {evaluationStatus === 'paused' && 'Paused'}
              </div>

              <Switch
                checked={rule.status === 'active'}
                onCheckedChange={handleToggle}
                aria-label={`Toggle ${rule.name}`}
              />

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => openEditSheet(rule)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleDuplicate}>
                    <Copy className="mr-2 h-4 w-4" />
                    Duplicate
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled>
                    <History className="mr-2 h-4 w-4" />
                    View History
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled>
                    <Play className="mr-2 h-4 w-4" />
                    Test Rule
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => setIsDeleteDialogOpen(true)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Status info */}
          <div className="mt-4 pt-3 border-t border-white/30 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              {rule.current_evaluation?.message && (
                <span>
                  Status:{' '}
                  <span className={rule.current_evaluation.status === 'healthy' ? 'text-lime-dark' : rule.current_evaluation.status === 'warning' ? 'text-amber-600' : 'text-tomato'}>
                    {rule.current_evaluation.message}
                  </span>
                </span>
              )}
              {!rule.current_evaluation?.message && rule.status === 'active' && (
                <span>Status: <span className="text-lime-dark">Monitoring</span></span>
              )}
              {rule.status === 'paused' && (
                <span>Status: Paused</span>
              )}
            </div>
            <div>
              {rule.last_triggered_at ? (
                <span>Last triggered: {formatRelativeTime(rule.last_triggered_at)}</span>
              ) : (
                <span>Never triggered</span>
              )}
            </div>
          </div>
        </NeuroCardContent>
      </NeuroCard>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Rule</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{rule.name}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
