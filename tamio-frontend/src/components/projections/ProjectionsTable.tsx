import { useState } from 'react';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { NeuroCard } from '@/components/ui/neuro-card';
import { Skeleton } from '@/components/ui/skeleton';
import { CollapsibleSection } from './CollapsibleSection';
import { ItemInsightDialog } from './ItemInsightDialog';
import type { ProjectionsTableData, ProjectionLineItem, ScenarioView, WeeklyAmount } from './types';
import { formatCurrency } from './types';

interface ProjectionsTableProps {
  data: ProjectionsTableData | null;
  scenarioView: ScenarioView;
  isLoading: boolean;
  disabledItems?: Set<string>;
  onToggleItem?: (itemId: string) => void;
}

function getValue(amount: WeeklyAmount, scenarioView: ScenarioView): number {
  switch (scenarioView) {
    case 'bestCase':
      return amount.bestCase;
    case 'worstCase':
      return amount.worstCase;
    default:
      return amount.expected;
  }
}

function ProjectionsTableSkeleton() {
  return (
    <NeuroCard className="p-0 overflow-hidden">
      <div className="p-4 space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    </NeuroCard>
  );
}

function EmptyState() {
  return (
    <NeuroCard className="p-8 text-center">
      <p className="text-muted-foreground">No projection data available.</p>
    </NeuroCard>
  );
}

export function ProjectionsTable({ data, scenarioView, isLoading, disabledItems, onToggleItem }: ProjectionsTableProps) {
  const [incomeExpanded, setIncomeExpanded] = useState(true);
  const [costsExpanded, setCostsExpanded] = useState(true);
  const [selectedItem, setSelectedItem] = useState<ProjectionLineItem | null>(null);

  if (isLoading) {
    return <ProjectionsTableSkeleton />;
  }

  if (!data) {
    return <EmptyState />;
  }

  return (
    <>
      <NeuroCard className="p-0 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30">
              <TableHead className="sticky left-0 bg-muted/30 z-20 min-w-[200px]">
                Item
              </TableHead>
              {data.weekNumbers.map((weekNum) => (
                <TableHead key={weekNum} className="text-center min-w-[100px]">
                  W{weekNum}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* Starting Balance Row */}
            <TableRow className="font-semibold bg-gray-50">
              <TableCell className="sticky left-0 bg-gray-50 z-10 min-w-[200px]">
                Starting balance
              </TableCell>
              {data.startingBalance.map((amount, i) => (
                <TableCell key={i} className="text-center min-w-[100px]">
                  {formatCurrency(getValue(amount, scenarioView))}
                </TableCell>
              ))}
            </TableRow>

            {/* Income Section */}
            <CollapsibleSection
              title="Income"
              items={data.incomeItems}
              totals={data.totalIncome}
              type="income"
              isExpanded={incomeExpanded}
              onToggle={() => setIncomeExpanded(!incomeExpanded)}
              scenarioView={scenarioView}
              onItemClick={setSelectedItem}
              disabledItems={disabledItems}
              onToggleItem={onToggleItem}
            />

            {/* Costs Section */}
            <CollapsibleSection
              title="Costs"
              items={data.costItems}
              totals={data.totalCosts}
              type="cost"
              isExpanded={costsExpanded}
              onToggle={() => setCostsExpanded(!costsExpanded)}
              scenarioView={scenarioView}
              onItemClick={setSelectedItem}
              disabledItems={disabledItems}
              onToggleItem={onToggleItem}
            />
          </TableBody>
        </Table>
      </NeuroCard>

      {/* Item Insight Dialog */}
      <ItemInsightDialog
        item={selectedItem}
        scenarioView={scenarioView}
        onClose={() => setSelectedItem(null)}
      />
    </>
  );
}
