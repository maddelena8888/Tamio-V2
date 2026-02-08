import { ClipboardList, Wallet, Users, Receipt } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NeuroCard, NeuroCardContent } from '@/components/ui/neuro-card';
import { useRules } from '@/contexts/RulesContext';

export function RuleEmptyState() {
  const { openCreateSheet } = useRules();

  return (
    <NeuroCard className="py-16">
      <NeuroCardContent className="flex flex-col items-center text-center">
        <div className="w-16 h-16 rounded-2xl bg-white/60 flex items-center justify-center mb-6">
          <ClipboardList className="h-8 w-8 text-gunmetal/60" />
        </div>

        <h2 className="font-league-spartan text-xl font-semibold text-gunmetal mb-2">
          No rules set up yet
        </h2>

        <p className="text-muted-foreground max-w-md mb-8">
          Rules automatically monitor your finances and alert you when something
          needs attention. Set up your first rule to start.
        </p>

        <Button onClick={openCreateSheet} className="rounded-full gap-2 mb-10">
          Create Your First Rule
        </Button>

        <div className="border-t border-white/30 pt-8 w-full max-w-lg">
          <p className="text-sm text-muted-foreground mb-4">
            Popular rules to start with:
          </p>
          <div className="space-y-3 text-left">
            <div className="flex items-center gap-3 text-sm">
              <div className="w-8 h-8 rounded-lg bg-white/50 flex items-center justify-center">
                <Wallet className="h-4 w-4 text-gunmetal" />
              </div>
              <div>
                <span className="font-medium text-gunmetal">Cash buffer alert</span>
                <span className="text-muted-foreground"> — Know before you run low</span>
              </div>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <div className="w-8 h-8 rounded-lg bg-white/50 flex items-center justify-center">
                <Users className="h-4 w-4 text-gunmetal" />
              </div>
              <div>
                <span className="font-medium text-gunmetal">Payroll coverage</span>
                <span className="text-muted-foreground"> — Never miss payroll</span>
              </div>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <div className="w-8 h-8 rounded-lg bg-white/50 flex items-center justify-center">
                <Receipt className="h-4 w-4 text-gunmetal" />
              </div>
              <div>
                <span className="font-medium text-gunmetal">VAT reserve</span>
                <span className="text-muted-foreground"> — Stay on top of tax</span>
              </div>
            </div>
          </div>
        </div>
      </NeuroCardContent>
    </NeuroCard>
  );
}
