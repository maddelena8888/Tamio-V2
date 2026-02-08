import { Wallet, Receipt, Users, FileText, TrendingUp, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { type RuleType, RULE_TYPES } from '@/lib/api/rules';

const RULE_ICONS: Record<RuleType, typeof Wallet> = {
  cash_buffer: Wallet,
  tax_vat_reserve: Receipt,
  payroll: Users,
  receivables: FileText,
  unusual_activity: TrendingUp,
};

interface RuleTypeSelectorProps {
  selectedType: RuleType | null;
  onSelect: (type: RuleType) => void;
}

export function RuleTypeSelector({ selectedType, onSelect }: RuleTypeSelectorProps) {
  return (
    <div className="space-y-3">
      {RULE_TYPES.map((ruleType) => {
        const Icon = RULE_ICONS[ruleType.type];
        const isSelected = selectedType === ruleType.type;

        return (
          <button
            key={ruleType.type}
            type="button"
            onClick={() => onSelect(ruleType.type)}
            className={cn(
              'w-full p-4 rounded-xl border-2 text-left transition-all',
              'hover:border-lime/50 hover:bg-white/30',
              isSelected
                ? 'border-lime bg-lime/10'
                : 'border-white/30 bg-white/20'
            )}
          >
            <div className="flex items-start gap-3">
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                isSelected ? 'bg-lime/20' : 'bg-white/50'
              )}>
                <Icon className={cn(
                  'h-5 w-5',
                  isSelected ? 'text-lime-dark' : 'text-gunmetal'
                )} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <h3 className={cn(
                    'font-medium',
                    isSelected ? 'text-lime-dark' : 'text-gunmetal'
                  )}>
                    {ruleType.title}
                  </h3>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-lime flex items-center justify-center">
                      <Check className="h-3 w-3 text-white" />
                    </div>
                  )}
                </div>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {ruleType.description}
                </p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
