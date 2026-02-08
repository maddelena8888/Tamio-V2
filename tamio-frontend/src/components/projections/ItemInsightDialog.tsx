import { MessageCircle, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTAMI } from '@/contexts/TAMIContext';
import type { ProjectionLineItem, ScenarioView } from './types';
import { formatCurrency } from './types';

interface ItemInsightDialogProps {
  item: ProjectionLineItem | null;
  scenarioView: ScenarioView;
  onClose: () => void;
}

export function ItemInsightDialog({ item, scenarioView, onClose }: ItemInsightDialogProps) {
  const { sendMessage, open: openTAMI } = useTAMI();

  if (!item) return null;

  const handleAskTAMI = () => {
    openTAMI();
    sendMessage(`Tell me more about the "${item.name}" ${item.type === 'income' ? 'income' : 'expense'} projection`);
    onClose();
  };

  const isIncome = item.type === 'income';
  const Icon = isIncome ? TrendingUp : TrendingDown;
  const colorClass = isIncome ? 'text-lime-dark' : 'text-tomato';
  const bgClass = isIncome ? 'bg-lime/10' : 'bg-tomato/10';

  // Calculate total amount based on scenario view
  const totalAmount = item.weeklyAmounts.reduce((sum, w) => {
    switch (scenarioView) {
      case 'bestCase':
        return sum + w.bestCase;
      case 'worstCase':
        return sum + w.worstCase;
      default:
        return sum + w.expected;
    }
  }, 0);

  // Get scenario label
  const scenarioLabel =
    scenarioView === 'bestCase' ? 'Best Case' : scenarioView === 'worstCase' ? 'Worst Case' : 'Expected';

  return (
    <Dialog open={!!item} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-1">
            <div className={cn('w-10 h-10 rounded-full flex items-center justify-center', bgClass)}>
              <Icon className={cn('w-5 h-5', colorClass)} />
            </div>
            <div>
              <DialogTitle>{item.name}</DialogTitle>
              <DialogDescription>
                {isIncome ? 'Income' : 'Cost'} projection details
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4">
          {/* Total Amount */}
          <div className="rounded-xl p-4 bg-muted/50">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <DollarSign className="w-4 h-4" />
              <span>Total {scenarioLabel} Forecast</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={cn('text-2xl font-bold', colorClass)}>
                {isIncome ? '+' : '-'}
                {formatCurrency(Math.abs(totalAmount))}
              </span>
              <span className="text-sm text-muted-foreground">over {item.weeklyAmounts.length} weeks</span>
            </div>
          </div>

          {/* Confidence */}
          <div>
            <h4 className="text-sm font-semibold mb-2">Confidence Level</h4>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'w-2 h-2 rounded-full',
                  item.confidence === 'high'
                    ? 'bg-lime-dark'
                    : item.confidence === 'medium'
                      ? 'bg-amber-500'
                      : 'bg-tomato'
                )}
              />
              <span className="text-sm capitalize">{item.confidence}</span>
            </div>
            {item.confidenceReason && (
              <p className="text-sm text-muted-foreground mt-1">{item.confidenceReason}</p>
            )}
          </div>

          {/* Category */}
          {item.category && (
            <div>
              <h4 className="text-sm font-semibold mb-2">Category</h4>
              <span className="text-sm text-muted-foreground capitalize">{item.category}</span>
            </div>
          )}

          {/* Source Type */}
          {item.sourceType && (
            <div>
              <h4 className="text-sm font-semibold mb-2">Source</h4>
              <span className="text-sm text-muted-foreground capitalize">{item.sourceType}</span>
            </div>
          )}

          {/* Weekly Breakdown (mini list) */}
          <div>
            <h4 className="text-sm font-semibold mb-2">Weekly Breakdown</h4>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {item.weeklyAmounts.map((week, i) => {
                const value =
                  scenarioView === 'bestCase'
                    ? week.bestCase
                    : scenarioView === 'worstCase'
                      ? week.worstCase
                      : week.expected;
                return (
                  <div key={i} className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Week {week.weekNumber}</span>
                    <span className={cn(colorClass)}>
                      {value > 0 ? formatCurrency(Math.abs(value)) : '$0'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Ask TAMI Button */}
          <Button onClick={handleAskTAMI} className="w-full" variant="outline">
            <MessageCircle className="w-4 h-4 mr-2" />
            Ask TAMI about this
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
