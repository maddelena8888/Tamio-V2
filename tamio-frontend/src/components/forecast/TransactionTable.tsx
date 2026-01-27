import { Link } from 'react-router-dom';
import { NeuroCard, NeuroCardContent, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { StatusBadge } from './StatusBadge';
import { cn } from '@/lib/utils';
import type { TransactionItem } from '@/lib/api/types';

interface TransactionTableProps {
  title: string;
  type: 'inflows' | 'outflows';
  transactions: TransactionItem[];
  onToggle: (transactionId: string, enabled: boolean) => void;
  className?: string;
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
};

export function TransactionTable({
  title,
  type,
  transactions,
  onToggle,
  className,
}: TransactionTableProps) {
  return (
    <NeuroCard className={className}>
      <NeuroCardHeader>
        <NeuroCardTitle>{title}</NeuroCardTitle>
      </NeuroCardHeader>
      <NeuroCardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Date</TableHead>
              <TableHead className="text-right w-[120px]">Amount</TableHead>
              <TableHead>{type === 'inflows' ? 'Client/Project' : 'Expense/Vendor'}</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[60px] text-center">Include</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No {type} found for this period
                </TableCell>
              </TableRow>
            ) : (
              transactions.map((transaction) => (
                <TableRow
                  key={transaction.id}
                  className={cn(
                    'transition-opacity',
                    !transaction.included && 'opacity-50'
                  )}
                >
                  <TableCell className="font-medium">
                    {formatDate(transaction.date)}
                  </TableCell>
                  <TableCell className={cn(
                    'text-right font-semibold',
                    type === 'inflows' ? 'text-lime-dark' : 'text-tomato'
                  )}>
                    {type === 'inflows' ? '+' : '-'}{formatCurrency(transaction.amount)}
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/clients?${transaction.entity_type}=${transaction.entity_id}`}
                      className="text-gunmetal hover:underline"
                    >
                      {transaction.name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={transaction.status} />
                  </TableCell>
                  <TableCell className="text-center">
                    <button
                      onClick={() => onToggle(transaction.id, !transaction.included)}
                      className={cn(
                        'relative inline-flex h-5 w-10 items-center rounded-full transition-colors',
                        transaction.included ? 'bg-lime' : 'bg-gray-300'
                      )}
                      aria-pressed={transaction.included}
                      role="switch"
                    >
                      <span
                        className={cn(
                          'inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform',
                          transaction.included ? 'translate-x-5' : 'translate-x-0.5'
                        )}
                      />
                    </button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </NeuroCardContent>
    </NeuroCard>
  );
}

export default TransactionTable;
