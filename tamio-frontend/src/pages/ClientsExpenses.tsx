import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardContent, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Plus, ArrowUpDown, Trash2, ExternalLink, CheckCircle, Pencil, Sparkles, AlertTriangle } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { getClients, createClient, updateClient, deleteClient } from '@/lib/api/data';
import { getExpenses, createExpense, updateExpense, deleteExpense } from '@/lib/api/data';
import { getForecast } from '@/lib/api/forecast';
import {
  getReconciliationSuggestions,
  getForecastImpact,
  getQueueSummary,
  approveReconciliation,
  rejectReconciliation,
} from '@/lib/api/reconciliation';
import {
  ForecastConfidenceBadge,
  ReconciliationSuggestionCard,
  ReconciliationTransactionTable,
} from '@/components/reconciliation';
import type {
  Client,
  ExpenseBucket,
  ClientType,
  ClientStatus,
  PaymentBehavior,
  RiskLevel,
  ExpenseCategory,
  BucketType,
  Priority,
  Frequency,
  Currency,
  ForecastResponse,
  ForecastEventSummary,
  ReconciliationSuggestion,
  ForecastImpactSummary,
  ReconciliationQueueSummary,
} from '@/lib/api/types';

interface Milestone {
  name: string;
  amount: string;
  expected_date: string;
  trigger_type: 'date_based' | 'delivery_based';
}

// Mock transaction data for demonstration
// Using 'as any' to bypass strict typing for demo purposes
const MOCK_TRANSACTIONS = [
  {
    id: 'txn-001',
    user_id: 'demo-user',
    obligation_id: 'obl-001',
    schedule_id: 'sched-001',
    payment_date: '2026-01-28',
    amount: '15000.00',
    currency: 'USD' as Currency,
    vendor_name: 'Acme Corp',
    reference: 'INV-2024-0142',
    source: 'bank_feed' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-28T14:30:00Z',
    created_at: '2026-01-28T14:00:00Z',
    updated_at: '2026-01-28T14:30:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'client_payment',
    ai_confidence: 0.98,
    matched_obligation_name: 'Acme Corp Monthly Retainer',
    matched_schedule: {
      id: 'sched-001',
      obligation_id: 'obl-001',
      due_date: '2026-01-25',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '15000.00',
      estimate_source: 'historical',
      confidence: 'high' as const,
      status: 'paid' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-28T14:30:00Z',
    },
  },
  {
    id: 'txn-002',
    user_id: 'demo-user',
    obligation_id: 'obl-002',
    schedule_id: 'sched-002',
    payment_date: '2026-01-27',
    amount: '4250.00',
    currency: 'USD' as Currency,
    vendor_name: 'AWS',
    reference: 'AWS-JAN-2026',
    source: 'xero_sync' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'credit_card',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-27T09:15:00Z',
    created_at: '2026-01-27T09:00:00Z',
    updated_at: '2026-01-27T09:15:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'infrastructure',
    ai_confidence: 0.96,
    matched_obligation_name: 'AWS Cloud Services',
    matched_schedule: {
      id: 'sched-002',
      obligation_id: 'obl-002',
      due_date: '2026-01-27',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '4000.00',
      estimate_source: 'historical',
      confidence: 'medium' as const,
      status: 'paid' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-27T09:15:00Z',
    },
  },
  {
    id: 'txn-003',
    user_id: 'demo-user',
    obligation_id: 'obl-003',
    schedule_id: 'sched-003',
    payment_date: '2026-01-26',
    amount: '8500.00',
    currency: 'USD' as Currency,
    vendor_name: 'TechStart Inc',
    reference: 'PROJ-M2-FINAL',
    source: 'bank_feed' as const,
    status: 'pending' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: false,
    reconciled_at: null,
    created_at: '2026-01-26T10:00:00Z',
    updated_at: null,
    reconciliation_status: 'ai_suggested' as const,
    ai_category: 'client_payment',
    ai_confidence: 0.87,
    matched_obligation_name: 'TechStart Website Redesign - Milestone 2',
    matched_schedule: {
      id: 'sched-003',
      obligation_id: 'obl-003',
      due_date: '2026-01-30',
      period_start: null,
      period_end: null,
      estimated_amount: '8000.00',
      estimate_source: 'contract',
      confidence: 'high' as const,
      status: 'pending' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
    },
  },
  {
    id: 'txn-004',
    user_id: 'demo-user',
    obligation_id: 'obl-004',
    schedule_id: 'sched-004',
    payment_date: '2026-01-25',
    amount: '1850.00',
    currency: 'USD' as Currency,
    vendor_name: 'Google Workspace',
    reference: 'GOOG-SUB-JAN',
    source: 'xero_sync' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'credit_card',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-25T16:00:00Z',
    created_at: '2026-01-25T15:30:00Z',
    updated_at: '2026-01-25T16:00:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'software',
    ai_confidence: 0.99,
    matched_obligation_name: 'Google Workspace Subscription',
    matched_schedule: {
      id: 'sched-004',
      obligation_id: 'obl-004',
      due_date: '2026-01-25',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '1850.00',
      estimate_source: 'fixed',
      confidence: 'high' as const,
      status: 'paid' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-25T16:00:00Z',
    },
  },
  {
    id: 'txn-005',
    user_id: 'demo-user',
    obligation_id: 'obl-005',
    schedule_id: 'sched-005',
    payment_date: '2026-01-24',
    amount: '22000.00',
    currency: 'USD' as Currency,
    vendor_name: 'GlobalRetail Co',
    reference: 'GR-Q1-ADV',
    source: 'bank_feed' as const,
    status: 'pending' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: false,
    reconciled_at: null,
    created_at: '2026-01-24T11:00:00Z',
    updated_at: null,
    reconciliation_status: 'ai_suggested' as const,
    ai_category: 'client_payment',
    ai_confidence: 0.74,
    matched_obligation_name: 'GlobalRetail Q1 Strategy Consulting',
    matched_schedule: {
      id: 'sched-005',
      obligation_id: 'obl-005',
      due_date: '2026-01-20',
      period_start: '2026-01-01',
      period_end: '2026-03-31',
      estimated_amount: '25000.00',
      estimate_source: 'contract',
      confidence: 'medium' as const,
      status: 'pending' as const,
      notes: 'Q1 advance payment - amount may vary',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
    },
  },
  {
    id: 'txn-006',
    user_id: 'demo-user',
    obligation_id: 'obl-006',
    schedule_id: 'sched-006',
    payment_date: '2026-01-23',
    amount: '3200.00',
    currency: 'USD' as Currency,
    vendor_name: 'WeWork',
    reference: 'WW-OFFICE-JAN',
    source: 'xero_sync' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-23T11:30:00Z',
    created_at: '2026-01-23T11:00:00Z',
    updated_at: '2026-01-23T11:30:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'office',
    ai_confidence: 0.95,
    matched_obligation_name: 'WeWork Office Space',
    matched_schedule: {
      id: 'sched-006',
      obligation_id: 'obl-006',
      due_date: '2026-01-23',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '3200.00',
      estimate_source: 'fixed',
      confidence: 'high' as const,
      status: 'paid' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-23T11:30:00Z',
    },
  },
  {
    id: 'txn-007',
    user_id: 'demo-user',
    obligation_id: null,
    schedule_id: null,
    payment_date: '2026-01-22',
    amount: '950.00',
    currency: 'USD' as Currency,
    vendor_name: 'Unknown Vendor',
    reference: 'TRANS-8847221',
    source: 'bank_feed' as const,
    status: 'pending' as const,
    account_id: null,
    payment_method: null,
    notes: null,
    is_reconciled: false,
    reconciled_at: null,
    created_at: '2026-01-22T14:00:00Z',
    updated_at: null,
    reconciliation_status: 'pending' as const,
    ai_category: undefined,
    ai_confidence: 0.32,
    matched_obligation_name: undefined,
    matched_schedule: undefined,
  },
  {
    id: 'txn-008',
    user_id: 'demo-user',
    obligation_id: 'obl-008',
    schedule_id: 'sched-008',
    payment_date: '2026-01-21',
    amount: '12500.00',
    currency: 'USD' as Currency,
    vendor_name: 'Zenith Media',
    reference: 'ZM-RETAINER-JAN',
    source: 'bank_feed' as const,
    status: 'pending' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: false,
    reconciled_at: null,
    created_at: '2026-01-21T09:00:00Z',
    updated_at: null,
    reconciliation_status: 'ai_suggested' as const,
    ai_category: 'client_payment',
    ai_confidence: 0.92,
    matched_obligation_name: 'Zenith Media Monthly Retainer',
    matched_schedule: {
      id: 'sched-008',
      obligation_id: 'obl-008',
      due_date: '2026-01-20',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '12500.00',
      estimate_source: 'historical',
      confidence: 'high' as const,
      status: 'pending' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
    },
  },
  {
    id: 'txn-009',
    user_id: 'demo-user',
    obligation_id: 'obl-009',
    schedule_id: 'sched-009',
    payment_date: '2026-01-20',
    amount: '675.00',
    currency: 'USD' as Currency,
    vendor_name: 'Slack',
    reference: 'SLACK-TEAM-JAN',
    source: 'xero_sync' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'credit_card',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-20T08:45:00Z',
    created_at: '2026-01-20T08:30:00Z',
    updated_at: '2026-01-20T08:45:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'software',
    ai_confidence: 0.97,
    matched_obligation_name: 'Slack Team Plan',
    matched_schedule: {
      id: 'sched-009',
      obligation_id: 'obl-009',
      due_date: '2026-01-20',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '675.00',
      estimate_source: 'fixed',
      confidence: 'high' as const,
      status: 'paid' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-20T08:45:00Z',
    },
  },
  {
    id: 'txn-010',
    user_id: 'demo-user',
    obligation_id: 'obl-010',
    schedule_id: 'sched-010',
    payment_date: '2026-01-19',
    amount: '5400.00',
    currency: 'USD' as Currency,
    vendor_name: 'Contractor Services LLC',
    reference: 'CS-INV-0089',
    source: 'bank_feed' as const,
    status: 'pending' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: false,
    reconciled_at: null,
    created_at: '2026-01-19T16:00:00Z',
    updated_at: null,
    reconciliation_status: 'pending' as const,
    ai_category: 'contractor',
    ai_confidence: 0.58,
    matched_obligation_name: 'Senior Developer Contractor',
    matched_schedule: {
      id: 'sched-010',
      obligation_id: 'obl-010',
      due_date: '2026-01-15',
      period_start: '2026-01-01',
      period_end: '2026-01-15',
      estimated_amount: '5000.00',
      estimate_source: 'contract',
      confidence: 'medium' as const,
      status: 'pending' as const,
      notes: 'Bi-weekly contractor payment - hours may vary',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
    },
  },
  {
    id: 'txn-011',
    user_id: 'demo-user',
    obligation_id: 'obl-011',
    schedule_id: 'sched-011',
    payment_date: '2026-01-18',
    amount: '18750.00',
    currency: 'USD' as Currency,
    vendor_name: 'BlueSky Ventures',
    reference: 'BSV-PROJ-PHASE1',
    source: 'bank_feed' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'bank_transfer',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-18T13:00:00Z',
    created_at: '2026-01-18T12:30:00Z',
    updated_at: '2026-01-18T13:00:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'client_payment',
    ai_confidence: 0.94,
    matched_obligation_name: 'BlueSky App Development - Phase 1',
    matched_schedule: {
      id: 'sched-011',
      obligation_id: 'obl-011',
      due_date: '2026-01-18',
      period_start: null,
      period_end: null,
      estimated_amount: '18750.00',
      estimate_source: 'contract',
      confidence: 'high' as const,
      status: 'paid' as const,
      notes: 'Phase 1 milestone payment',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-18T13:00:00Z',
    },
  },
  {
    id: 'txn-012',
    user_id: 'demo-user',
    obligation_id: 'obl-012',
    schedule_id: 'sched-012',
    payment_date: '2026-01-17',
    amount: '2100.00',
    currency: 'USD' as Currency,
    vendor_name: 'Figma Inc',
    reference: 'FIG-ORG-JAN',
    source: 'xero_sync' as const,
    status: 'completed' as const,
    account_id: null,
    payment_method: 'credit_card',
    notes: null,
    is_reconciled: true,
    reconciled_at: '2026-01-17T10:20:00Z',
    created_at: '2026-01-17T10:00:00Z',
    updated_at: '2026-01-17T10:20:00Z',
    reconciliation_status: 'reconciled' as const,
    ai_category: 'software',
    ai_confidence: 0.98,
    matched_obligation_name: 'Figma Organization Plan',
    matched_schedule: {
      id: 'sched-012',
      obligation_id: 'obl-012',
      due_date: '2026-01-17',
      period_start: '2026-01-01',
      period_end: '2026-01-31',
      estimated_amount: '2100.00',
      estimate_source: 'fixed',
      confidence: 'high' as const,
      status: 'paid' as const,
      notes: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-17T10:20:00Z',
    },
  },
];

export default function ClientsExpenses() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [clients, setClients] = useState<Client[]>([]);
  const [expenses, setExpenses] = useState<ExpenseBucket[]>([]);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'transactions');
  const [highlightedId, setHighlightedId] = useState<string | null>(searchParams.get('highlight'));

  // Client form state
  const [isClientDialogOpen, setIsClientDialogOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [isClientViewMode, setIsClientViewMode] = useState(true);
  const [clientForm, setClientForm] = useState({
    // Core info
    name: '',
    client_type: 'retainer' as ClientType,
    currency: 'USD' as Currency,
    status: 'active' as ClientStatus,
    // Risk indicators
    payment_behavior: 'on_time' as PaymentBehavior,
    churn_risk: 'low' as RiskLevel,
    scope_risk: 'low' as RiskLevel,
    // Billing - common
    amount: '',
    frequency: 'monthly' as Frequency,
    day_of_month: '1',
    payment_terms: 'net_30',
    // Project-specific
    total_project_value: '',
    milestones: [] as Milestone[],
    // Usage-specific
    typical_amount: '',
    // Notes
    notes: '',
  });

  // Save operation state
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Xero sync success dialog state
  const [xeroSyncDialog, setXeroSyncDialog] = useState<{
    isOpen: boolean;
    name: string;
    type: 'client' | 'expense';
    xeroContactId: string | null;
  }>({ isOpen: false, name: '', type: 'client', xeroContactId: null });

  // Expense form state
  const [isExpenseDialogOpen, setIsExpenseDialogOpen] = useState(false);
  const [editingExpense, setEditingExpense] = useState<ExpenseBucket | null>(null);
  const [isExpenseViewMode, setIsExpenseViewMode] = useState(true);
  const [expenseForm, setExpenseForm] = useState({
    name: '',
    category: 'other' as ExpenseCategory,
    bucket_type: 'fixed' as BucketType,
    monthly_amount: '',
    priority: 'medium' as Priority,
    employee_count: '',
  });

  // Client filter/sort state
  type ClientSortOption = 'amount' | 'due_date' | 'client_type' | 'risk_score';
  const [clientSort, setClientSort] = useState<ClientSortOption>('amount');

  // Expense filter/sort state
  type ExpenseSortOption = 'amount' | 'due_date' | 'priority' | 'bucket_type';
  const [expenseSort, setExpenseSort] = useState<ExpenseSortOption>('amount');

  // Reconciliation state
  const [reconciliationSuggestions, setReconciliationSuggestions] = useState<ReconciliationSuggestion[]>([]);
  const [forecastImpact, setForecastImpact] = useState<ForecastImpactSummary | null>(null);
  const [queueSummary, setQueueSummary] = useState<ReconciliationQueueSummary | null>(null);
  const [isReconciliationLoading, setIsReconciliationLoading] = useState(false);

  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const [clientsData, expensesData, forecastData] = await Promise.all([
          getClients(user.id),
          getExpenses(user.id),
          getForecast(user.id).catch(() => null),
        ]);
        setClients(clientsData);
        setExpenses(expensesData);
        setForecast(forecastData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user]);

  // Fetch reconciliation data when queue tab is active
  useEffect(() => {
    if (!user || (activeTab !== 'reconciliation' && activeTab !== 'transactions')) return;

    const fetchReconciliationData = async () => {
      setIsReconciliationLoading(true);
      try {
        const [suggestionsData, impactData, summaryData] = await Promise.all([
          getReconciliationSuggestions(false).catch(() => ({ suggestions: [], total_count: 0, auto_approved_count: 0, pending_review_count: 0, unmatched_count: 0 })),
          getForecastImpact().catch(() => null),
          getQueueSummary().catch(() => null),
        ]);
        setReconciliationSuggestions(suggestionsData.suggestions);
        setForecastImpact(impactData);
        setQueueSummary(summaryData);
      } catch (error) {
        console.error('Failed to fetch reconciliation data:', error);
      } finally {
        setIsReconciliationLoading(false);
      }
    };

    fetchReconciliationData();
  }, [user, activeTab]);

  // Handle URL params for highlighting
  useEffect(() => {
    const tab = searchParams.get('tab');
    const highlight = searchParams.get('highlight');

    if (tab) {
      setActiveTab(tab);
    }
    if (highlight) {
      setHighlightedId(highlight);
      // Clear highlight after animation and remove from URL
      const timer = setTimeout(() => {
        setHighlightedId(null);
        setSearchParams({}, { replace: true });
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [searchParams, setSearchParams]);

  // Client handlers
  const handleOpenClientDialog = (client?: Client, viewMode = false) => {
    if (client) {
      setEditingClient(client);
      setClientForm({
        // Core info
        name: client.name,
        client_type: client.client_type,
        currency: client.currency,
        status: client.status,
        // Risk indicators
        payment_behavior: client.payment_behavior,
        churn_risk: client.churn_risk,
        scope_risk: client.scope_risk,
        // Billing - common
        amount: client.billing_config.amount || '',
        frequency: (client.billing_config.frequency as Frequency) || 'monthly',
        day_of_month: client.billing_config.day_of_month?.toString() || '1',
        payment_terms: client.billing_config.payment_terms || 'net_30',
        // Project-specific
        total_project_value: '',
        milestones: client.billing_config.milestones || [],
        // Usage-specific
        typical_amount: client.client_type === 'usage' ? (client.billing_config.amount || '') : '',
        // Notes
        notes: client.notes || '',
      });
      setIsClientViewMode(viewMode);
    } else {
      setEditingClient(null);
      setClientForm({
        name: '',
        client_type: 'retainer',
        currency: 'USD',
        status: 'active',
        payment_behavior: 'on_time',
        churn_risk: 'low',
        scope_risk: 'low',
        amount: '',
        frequency: 'monthly',
        day_of_month: '1',
        payment_terms: 'net_30',
        total_project_value: '',
        milestones: [],
        typical_amount: '',
        notes: '',
      });
      setIsClientViewMode(false);
    }
    setIsClientDialogOpen(true);
  };

  const handleSaveClient = async () => {
    if (!user) {
      setSaveError('You must be logged in to add a client');
      return;
    }

    if (!clientForm.name.trim()) {
      setSaveError('Client name is required');
      return;
    }

    setSaveError(null);
    setIsSaving(true);

    // Build billing config based on client type
    const buildBillingConfig = () => {
      const baseConfig = {
        day_of_month: parseInt(clientForm.day_of_month) || 1,
        payment_terms: clientForm.payment_terms,
      };

      switch (clientForm.client_type) {
        case 'retainer':
          return {
            ...baseConfig,
            amount: clientForm.amount,
            frequency: clientForm.frequency,
          };
        case 'project':
          return {
            ...baseConfig,
            amount: clientForm.total_project_value || clientForm.amount,
            milestones: clientForm.milestones,
          };
        case 'usage':
          return {
            ...baseConfig,
            amount: clientForm.typical_amount || clientForm.amount,
            frequency: clientForm.frequency,
          };
        case 'mixed':
          return {
            ...baseConfig,
            amount: clientForm.amount,
            frequency: clientForm.frequency,
            milestones: clientForm.milestones,
          };
        default:
          return {
            ...baseConfig,
            amount: clientForm.amount,
            frequency: clientForm.frequency,
          };
      }
    };

    try {
      if (editingClient) {
        const response = await updateClient(editingClient.id, {
          name: clientForm.name,
          client_type: clientForm.client_type,
          currency: clientForm.currency,
          status: clientForm.status,
          payment_behavior: clientForm.payment_behavior,
          churn_risk: clientForm.churn_risk,
          scope_risk: clientForm.scope_risk,
          billing_config: buildBillingConfig(),
          notes: clientForm.notes || undefined,
        });
        setClients(clients.map((c) => (c.id === editingClient.id ? response.client : c)));
      } else {
        const response = await createClient({
          user_id: user.id,
          name: clientForm.name,
          client_type: clientForm.client_type,
          currency: clientForm.currency,
          status: clientForm.status,
          payment_behavior: clientForm.payment_behavior,
          churn_risk: clientForm.churn_risk,
          scope_risk: clientForm.scope_risk,
          billing_config: buildBillingConfig(),
          notes: clientForm.notes || undefined,
        });
        setClients([...clients, response.client]);

        // Show Xero sync success dialog if client was synced
        if (response.client.xero_contact_id && response.client.sync_status === 'synced') {
          setXeroSyncDialog({
            isOpen: true,
            name: response.client.name,
            type: 'client',
            xeroContactId: response.client.xero_contact_id,
          });
        }

        // Reset form after successful create
        setClientForm({
          name: '',
          client_type: 'retainer',
          currency: 'USD',
          status: 'active',
          payment_behavior: 'on_time',
          churn_risk: 'low',
          scope_risk: 'low',
          amount: '',
          frequency: 'monthly',
          day_of_month: '1',
          payment_terms: 'net_30',
          total_project_value: '',
          milestones: [],
          typical_amount: '',
          notes: '',
        });
      }
      setIsClientDialogOpen(false);
    } catch (error) {
      console.error('Failed to save client:', error);
      setSaveError(error instanceof Error ? error.message : 'Failed to save client');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteClient = async (clientId: string) => {
    try {
      await deleteClient(clientId);
      setClients(clients.filter((c) => c.id !== clientId));
    } catch (error) {
      console.error('Failed to delete client:', error);
    }
  };

  // Expense handlers
  const handleOpenExpenseDialog = (expense?: ExpenseBucket, viewMode = false) => {
    if (expense) {
      setEditingExpense(expense);
      setExpenseForm({
        name: expense.name,
        category: expense.category,
        bucket_type: expense.bucket_type,
        monthly_amount: expense.monthly_amount,
        priority: expense.priority as Priority,
        employee_count: expense.employee_count?.toString() || '',
      });
      setIsExpenseViewMode(viewMode);
    } else {
      setEditingExpense(null);
      setExpenseForm({
        name: '',
        category: 'other',
        bucket_type: 'fixed',
        monthly_amount: '',
        priority: 'medium',
        employee_count: '',
      });
      setIsExpenseViewMode(false);
    }
    setIsExpenseDialogOpen(true);
  };

  const handleSaveExpense = async () => {
    if (!user) return;

    try {
      if (editingExpense) {
        const response = await updateExpense(editingExpense.id, {
          name: expenseForm.name,
          category: expenseForm.category,
          bucket_type: expenseForm.bucket_type,
          monthly_amount: expenseForm.monthly_amount,
          priority: expenseForm.priority,
          employee_count: expenseForm.employee_count
            ? parseInt(expenseForm.employee_count)
            : undefined,
        });
        setExpenses(expenses.map((e) => (e.id === editingExpense.id ? response.bucket : e)));
      } else {
        const response = await createExpense({
          user_id: user.id,
          name: expenseForm.name,
          category: expenseForm.category,
          bucket_type: expenseForm.bucket_type,
          monthly_amount: expenseForm.monthly_amount,
          currency: 'USD',
          priority: expenseForm.priority,
          is_stable: expenseForm.bucket_type === 'fixed',
          due_day: 15,
          frequency: 'monthly',
          employee_count: expenseForm.employee_count
            ? parseInt(expenseForm.employee_count)
            : undefined,
        });
        setExpenses([...expenses, response.bucket]);

        // Show Xero sync success dialog if expense was synced
        if (response.bucket.xero_contact_id && response.bucket.sync_status === 'synced') {
          setXeroSyncDialog({
            isOpen: true,
            name: response.bucket.name,
            type: 'expense',
            xeroContactId: response.bucket.xero_contact_id,
          });
        }
      }
      setIsExpenseDialogOpen(false);
    } catch (error) {
      console.error('Failed to save expense:', error);
    }
  };

  const handleDeleteExpense = async (bucketId: string) => {
    try {
      await deleteExpense(bucketId);
      setExpenses(expenses.filter((e) => e.id !== bucketId));
    } catch (error) {
      console.error('Failed to delete expense:', error);
    }
  };

  // Reconciliation handlers
  const handleApproveReconciliation = useCallback(async (suggestion: ReconciliationSuggestion) => {
    try {
      await approveReconciliation({
        suggestion_id: suggestion.id,
        payment_id: suggestion.payment_id,
        schedule_id: suggestion.suggested_schedule_id,
      });
      // Remove from suggestions list
      setReconciliationSuggestions((prev) =>
        prev.filter((s) => s.id !== suggestion.id)
      );
      // Update queue summary
      if (queueSummary) {
        setQueueSummary({
          ...queueSummary,
          total_pending: queueSummary.total_pending - 1,
          ai_suggestions: queueSummary.ai_suggestions - 1,
        });
      }
      toast.success('Match approved', {
        description: `${suggestion.payment.vendor_name || 'Transaction'} matched to ${suggestion.suggested_obligation.vendor_name || suggestion.suggested_obligation.category}`,
      });
    } catch (error) {
      console.error('Failed to approve reconciliation:', error);
      toast.error('Failed to approve match');
    }
  }, [queueSummary]);

  const handleRejectReconciliation = useCallback(async (suggestion: ReconciliationSuggestion) => {
    try {
      await rejectReconciliation({
        payment_id: suggestion.payment_id,
      });
      // Remove from suggestions list
      setReconciliationSuggestions((prev) =>
        prev.filter((s) => s.id !== suggestion.id)
      );
      // Update queue summary
      if (queueSummary) {
        setQueueSummary({
          ...queueSummary,
          total_pending: queueSummary.total_pending - 1,
          ai_suggestions: Math.max(0, queueSummary.ai_suggestions - 1),
        });
      }
      toast.success('Suggestion rejected');
    } catch (error) {
      console.error('Failed to reject reconciliation:', error);
      toast.error('Failed to reject suggestion');
    }
  }, [queueSummary]);

  const handleEditReconciliation = useCallback((_suggestion: ReconciliationSuggestion) => {
    // TODO: Open edit modal to reassign to different obligation
    toast.info('Edit functionality coming soon');
  }, []);

  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
  };

  // Get display amount for a client based on client type
  const getClientDisplayAmount = (client: Client): string => {
    const config = client.billing_config;

    switch (client.client_type) {
      case 'project':
        // For projects, use total_value or sum of milestones
        if (config.total_value) return config.total_value;
        if (config.milestones && config.milestones.length > 0) {
          const total = config.milestones.reduce((sum, m) => sum + parseFloat(m.amount || '0'), 0);
          return total.toString();
        }
        return config.amount || '0';
      case 'usage':
        // For usage, use typical_amount or amount
        return config.typical_amount || config.amount || '0';
      default:
        // For retainer and mixed, use amount
        return config.amount || '0';
    }
  };

  // Get display frequency for a client
  const getClientDisplayFrequency = (client: Client): string => {
    if (client.client_type === 'project') {
      return 'total';
    }
    return client.billing_config.frequency || 'monthly';
  };

  // Risk score calculation (average of payment, churn, scope risks)
  const getRiskScore = (client: Client): number => {
    const riskValues: Record<string, number> = {
      low: 1,
      medium: 2,
      high: 3,
      on_time: 1,
      delayed: 3,
      unknown: 2,
    };
    const paymentRisk = riskValues[client.payment_behavior] || 2;
    const churnRisk = riskValues[client.churn_risk] || 1;
    const scopeRisk = riskValues[client.scope_risk] || 1;
    return (paymentRisk + churnRisk + scopeRisk) / 3;
  };

  // Client type order for sorting (retainer > project > usage > mixed)
  const clientTypeOrder: Record<ClientType, number> = {
    retainer: 1,
    project: 2,
    usage: 3,
    mixed: 4,
  };

  // Priority order for sorting (essential > important > discretionary)
  const priorityOrder: Record<string, number> = {
    essential: 1,
    high: 1,
    important: 2,
    medium: 2,
    discretionary: 3,
    low: 3,
  };

  // Sorted clients
  const sortedClients = [...clients]
    .filter((c) => c.status !== 'deleted')
    .sort((a, b) => {
      switch (clientSort) {
        case 'amount':
          return parseFloat(getClientDisplayAmount(b)) - parseFloat(getClientDisplayAmount(a));
        case 'due_date':
          return (a.billing_config.day_of_month || 1) - (b.billing_config.day_of_month || 1);
        case 'client_type':
          return clientTypeOrder[a.client_type] - clientTypeOrder[b.client_type];
        case 'risk_score':
          return getRiskScore(b) - getRiskScore(a);
        default:
          return 0;
      }
    });

  // Sorted expenses
  const sortedExpenses = [...expenses].sort((a, b) => {
    switch (expenseSort) {
      case 'amount':
        return parseFloat(b.monthly_amount) - parseFloat(a.monthly_amount);
      case 'due_date':
        return (a.due_day || 1) - (b.due_day || 1);
      case 'priority':
        return priorityOrder[a.priority] - priorityOrder[b.priority];
      case 'bucket_type':
        return a.bucket_type === 'fixed' ? -1 : 1;
      default:
        return 0;
    }
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Ledger</h1>
        {/* Forecast Accuracy Badge */}
        {forecastImpact && (
          <ForecastConfidenceBadge
            score={forecastImpact.accuracy_score}
            unreconciledCount={forecastImpact.unreconciled_count}
            size="md"
          />
        )}
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex items-center justify-between">
          <TabsList className="glass-strong !h-11 !p-1 !rounded-xl gap-1 w-fit shadow-lg shadow-black/5 !bg-white/85">
            <TabsTrigger
              value="transactions"
              className="!rounded-lg !px-5 !py-1.5 !h-auto text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:!bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80 !border-0"
            >
              Transactions
            </TabsTrigger>
            <TabsTrigger
              value="reconciliation"
              className="!rounded-lg !px-5 !py-1.5 !h-auto text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:!bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80 !border-0 relative"
            >
              <span className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Reconciliation
                {queueSummary && queueSummary.total_pending > 0 && (
                  <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-mimi-pink text-[10px] font-bold text-white">
                    {queueSummary.total_pending > 9 ? '9+' : queueSummary.total_pending}
                  </span>
                )}
              </span>
            </TabsTrigger>
            <TabsTrigger
              value="clients"
              className="!rounded-lg !px-5 !py-1.5 !h-auto text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:!bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80 !border-0"
            >
              Clients
            </TabsTrigger>
            <TabsTrigger
              value="expenses"
              className="!rounded-lg !px-5 !py-1.5 !h-auto text-sm font-semibold text-gunmetal/60 transition-all duration-300 data-[state=active]:!bg-white data-[state=active]:text-gunmetal data-[state=active]:shadow-md data-[state=active]:shadow-black/5 hover:text-gunmetal/80 !border-0"
            >
              Expenses
            </TabsTrigger>
          </TabsList>

          {/* Sort Controls - shown based on active tab */}
          {activeTab === 'clients' && (
            <div className="flex items-center gap-2">
              <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Sort by:</span>
              <Select
                value={clientSort}
                onValueChange={(v: typeof clientSort) => setClientSort(v)}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="amount">Amount (High to Low)</SelectItem>
                  <SelectItem value="due_date">Due Date (Earliest)</SelectItem>
                  <SelectItem value="client_type">Type (Retainer First)</SelectItem>
                  <SelectItem value="risk_score">Risk Score (High to Low)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {activeTab === 'expenses' && (
            <div className="flex items-center gap-2">
              <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Sort by:</span>
              <Select
                value={expenseSort}
                onValueChange={(v: typeof expenseSort) => setExpenseSort(v)}
              >
                <SelectTrigger className="w-[220px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="amount">Amount (High to Low)</SelectItem>
                  <SelectItem value="due_date">Due Date (Earliest)</SelectItem>
                  <SelectItem value="priority">Priority (High to Low)</SelectItem>
                  <SelectItem value="bucket_type">Type (Fixed First)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {/* Clients Tab */}
        <TabsContent value="clients" className="space-y-4">

          {sortedClients.map((client) => (
            <NeuroCard
              key={client.id}
              className={`p-4 transition-all duration-500 ${
                highlightedId === client.id
                  ? 'ring-2 ring-lime-dark ring-offset-2 bg-lime-dark/5'
                  : ''
              }`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-lg">{client.name}</h3>
                      {/* Xero sync status badge with tooltip */}
                      {client.xero_contact_id ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="outline"
                              className={`cursor-help ${
                                client.xero_repeating_invoice_id
                                  ? 'border-green-500 text-green-600 bg-green-50'
                                  : client.sync_status === 'synced'
                                  ? 'border-blue-500 text-blue-600 bg-blue-50'
                                  : client.sync_status === 'error'
                                  ? 'border-red-500 text-red-600 bg-red-50'
                                  : 'border-yellow-500 text-yellow-600 bg-yellow-50'
                              }`}
                            >
                              {client.xero_repeating_invoice_id
                                ? 'Xero Invoice'
                                : client.sync_status === 'synced'
                                ? 'Xero Synced'
                                : client.sync_status === 'error'
                                ? 'Xero Error'
                                : 'Xero Pending'}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            {client.xero_repeating_invoice_id
                              ? 'Linked to Xero with a repeating invoice. Strongest revenue certainty.'
                              : client.sync_status === 'synced'
                              ? 'Synced to Xero as a contact. Create an invoice in Xero to strengthen revenue certainty.'
                              : client.sync_status === 'error'
                              ? 'Failed to sync with Xero. Check your connection and try again.'
                              : 'Waiting to sync with Xero.'}
                          </TooltipContent>
                        </Tooltip>
                      ) : client.source === 'xero' ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant="outline" className="cursor-help border-blue-500 text-blue-600 bg-blue-50">
                              From Xero
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            Imported from Xero. This client exists in your Xero account.
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant="outline" className="cursor-help border-gray-300 text-gray-500 bg-gray-50">
                              Not Synced
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            Not linked to accounting software. Create this client in Xero or QuickBooks to sync revenue data.
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Type: {client.client_type} | {client.currency} | {client.status}
                    </p>
                    <p className="text-lg font-medium">
                      {formatCurrency(getClientDisplayAmount(client))}/
                      {getClientDisplayFrequency(client)}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
                      <span>
                        Payment:{' '}
                        <span
                          className={
                            client.payment_behavior === 'delayed'
                              ? 'text-tomato'
                              : 'text-foreground'
                          }
                        >
                          {client.payment_behavior}
                        </span>
                      </span>
                      <span>
                        Churn risk:{' '}
                        <span
                          className={
                            client.churn_risk === 'high'
                              ? 'text-tomato'
                              : client.churn_risk === 'medium'
                              ? 'text-mimi-pink'
                              : ''
                          }
                        >
                          {client.churn_risk}
                        </span>
                      </span>
                      <span>
                        Scope risk:{' '}
                        <span
                          className={
                            client.scope_risk === 'high'
                              ? 'text-tomato'
                              : client.scope_risk === 'medium'
                              ? 'text-mimi-pink'
                              : ''
                          }
                        >
                          {client.scope_risk}
                        </span>
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleOpenClientDialog(client)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteClient(client.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            </NeuroCard>
          ))}

          {/* Add Client Form */}
          <NeuroCard className="border-dashed">
            <NeuroCardHeader>
              <NeuroCardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Add New Client
              </NeuroCardTitle>
            </NeuroCardHeader>
            <NeuroCardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Client Name</Label>
                  <Input
                    placeholder="e.g., Acme Corp"
                    value={clientForm.name}
                    onChange={(e) => setClientForm({ ...clientForm, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Client Type</Label>
                  <Select
                    value={clientForm.client_type}
                    onValueChange={(v: ClientType) =>
                      setClientForm({ ...clientForm, client_type: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="retainer">Retainer</SelectItem>
                      <SelectItem value="project">Project</SelectItem>
                      <SelectItem value="usage">Usage-based</SelectItem>
                      <SelectItem value="mixed">Mixed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Payment Behavior</Label>
                  <Select
                    value={clientForm.payment_behavior}
                    onValueChange={(v: PaymentBehavior) =>
                      setClientForm({ ...clientForm, payment_behavior: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="on_time">On Time</SelectItem>
                      <SelectItem value="delayed">Delayed</SelectItem>
                      <SelectItem value="unknown">Unknown</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Churn Risk</Label>
                  <Select
                    value={clientForm.churn_risk}
                    onValueChange={(v: RiskLevel) =>
                      setClientForm({ ...clientForm, churn_risk: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Billing Frequency</Label>
                  <Select
                    value={clientForm.frequency}
                    onValueChange={(v: Frequency) =>
                      setClientForm({ ...clientForm, frequency: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="monthly">Monthly</SelectItem>
                      <SelectItem value="quarterly">Quarterly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Amount</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={clientForm.amount}
                    onChange={(e) => setClientForm({ ...clientForm, amount: e.target.value })}
                  />
                </div>
              </div>
              {saveError && (
                <p className="text-sm text-destructive mt-2">{saveError}</p>
              )}
              <Button className="mt-4" onClick={handleSaveClient} disabled={isSaving}>
                <Plus className="h-4 w-4 mr-2" />
                {isSaving ? 'Adding...' : 'Add Client'}
              </Button>
            </NeuroCardContent>
          </NeuroCard>
        </TabsContent>

        {/* Expenses Tab */}
        <TabsContent value="expenses" className="space-y-4">
          {sortedExpenses.map((expense) => (
            <NeuroCard
              key={expense.id}
              className={`p-4 transition-all duration-500 ${
                highlightedId === expense.id
                  ? 'ring-2 ring-tomato ring-offset-2 bg-tomato/5'
                  : ''
              }`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-lg">{expense.name}</h3>
                      <Badge variant="outline">{expense.category}</Badge>
                      <Badge
                        variant={expense.bucket_type === 'fixed' ? 'secondary' : 'outline'}
                      >
                        {expense.bucket_type}
                      </Badge>
                      {/* Xero sync status badge with tooltip */}
                      {expense.xero_contact_id ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="outline"
                              className={`cursor-help ${
                                expense.xero_repeating_bill_id
                                  ? 'border-green-500 text-green-600 bg-green-50'
                                  : expense.sync_status === 'synced'
                                  ? 'border-blue-500 text-blue-600 bg-blue-50'
                                  : expense.sync_status === 'error'
                                  ? 'border-red-500 text-red-600 bg-red-50'
                                  : 'border-yellow-500 text-yellow-600 bg-yellow-50'
                              }`}
                            >
                              {expense.xero_repeating_bill_id
                                ? 'Xero Bill'
                                : expense.sync_status === 'synced'
                                ? 'Xero Synced'
                                : expense.sync_status === 'error'
                                ? 'Xero Error'
                                : 'Xero Pending'}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            {expense.xero_repeating_bill_id
                              ? 'Linked to Xero with a repeating bill. Strongest expense certainty.'
                              : expense.sync_status === 'synced'
                              ? 'Synced to Xero as a supplier. Create a bill in Xero to strengthen expense tracking.'
                              : expense.sync_status === 'error'
                              ? 'Failed to sync with Xero. Check your connection and try again.'
                              : 'Waiting to sync with Xero.'}
                          </TooltipContent>
                        </Tooltip>
                      ) : expense.source === 'xero' ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant="outline" className="cursor-help border-blue-500 text-blue-600 bg-blue-50">
                              From Xero
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            Imported from Xero. This supplier exists in your Xero account.
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Badge variant="outline" className="cursor-help border-gray-300 text-gray-500 bg-gray-50">
                              Not Synced
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            Not linked to accounting software. Create this supplier in Xero or QuickBooks to sync expense data.
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                    <p className="text-lg font-medium">
                      {formatCurrency(expense.monthly_amount)}/{expense.frequency}
                    </p>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground mt-2">
                      <span>
                        Due:{' '}
                        <span className="text-foreground font-medium">
                          {expense.due_day === 1
                            ? '1st'
                            : expense.due_day === 2
                            ? '2nd'
                            : expense.due_day === 3
                            ? '3rd'
                            : `${expense.due_day}th`}{' '}
                          of month
                        </span>
                      </span>
                      <span>
                        Priority:{' '}
                        <span
                          className={
                            expense.priority === 'essential' || expense.priority === 'high'
                              ? 'text-foreground font-medium'
                              : ''
                          }
                        >
                          {expense.priority}
                        </span>
                      </span>
                      {expense.employee_count && (
                        <span>Employees: {expense.employee_count}</span>
                      )}
                      <span>
                        Stability:{' '}
                        {expense.is_stable ? 'Stable' : 'Varies'}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleOpenExpenseDialog(expense)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteExpense(expense.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </div>
            </NeuroCard>
          ))}

          {/* Add Expense Form */}
          <NeuroCard className="border-dashed">
            <NeuroCardHeader>
              <NeuroCardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Add New Expense
              </NeuroCardTitle>
            </NeuroCardHeader>
            <NeuroCardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    placeholder="e.g., Payroll"
                    value={expenseForm.name}
                    onChange={(e) => setExpenseForm({ ...expenseForm, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select
                    value={expenseForm.category}
                    onValueChange={(v: ExpenseCategory) =>
                      setExpenseForm({ ...expenseForm, category: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="payroll">Payroll</SelectItem>
                      <SelectItem value="rent">Rent / Office</SelectItem>
                      <SelectItem value="contractors">Contractors</SelectItem>
                      <SelectItem value="software">Software & Tools</SelectItem>
                      <SelectItem value="marketing">Marketing</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Monthly Amount</Label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={expenseForm.monthly_amount}
                    onChange={(e) =>
                      setExpenseForm({ ...expenseForm, monthly_amount: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select
                    value={expenseForm.bucket_type}
                    onValueChange={(v: BucketType) =>
                      setExpenseForm({ ...expenseForm, bucket_type: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fixed">Fixed (hard to change)</SelectItem>
                      <SelectItem value="variable">Variable (adjustable)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select
                    value={expenseForm.priority}
                    onValueChange={(v: Priority) =>
                      setExpenseForm({ ...expenseForm, priority: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="essential">Essential</SelectItem>
                      <SelectItem value="important">Important</SelectItem>
                      <SelectItem value="discretionary">Discretionary</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {expenseForm.category === 'payroll' && (
                  <div className="space-y-2">
                    <Label>Number of Employees</Label>
                    <Input
                      type="number"
                      placeholder="0"
                      value={expenseForm.employee_count}
                      onChange={(e) =>
                        setExpenseForm({ ...expenseForm, employee_count: e.target.value })
                      }
                    />
                  </div>
                )}
              </div>
              <Button className="mt-4" onClick={handleSaveExpense}>
                <Plus className="h-4 w-4 mr-2" />
                Add Expense
              </Button>
            </NeuroCardContent>
          </NeuroCard>
        </TabsContent>

        {/* Transactions Tab - Past Data with AI Reconciliation */}
        <TabsContent value="transactions" className="space-y-4">
          {/* Summary Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm p-4">
              <p className="text-2xl font-bold text-gunmetal">{MOCK_TRANSACTIONS.length}</p>
              <p className="text-xs text-gray-500">Total Transactions</p>
            </div>
            <div className="rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm p-4">
              <p className="text-2xl font-bold text-lime-dark">
                {MOCK_TRANSACTIONS.filter((t) => t.reconciliation_status === 'reconciled').length}
              </p>
              <p className="text-xs text-gray-500">Reconciled</p>
            </div>
            <div className="rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm p-4">
              <p className="text-2xl font-bold text-mimi-pink">
                {MOCK_TRANSACTIONS.filter((t) => t.reconciliation_status === 'ai_suggested').length}
              </p>
              <p className="text-xs text-gray-500">AI Suggestions</p>
            </div>
            <div className="rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm p-4">
              <p className="text-2xl font-bold text-amber-600">
                {MOCK_TRANSACTIONS.filter((t) => t.reconciliation_status === 'pending').length}
              </p>
              <p className="text-xs text-gray-500">Needs Review</p>
            </div>
          </div>

          {/* Transaction Table */}
          <ReconciliationTransactionTable
            transactions={MOCK_TRANSACTIONS as any}
            isLoading={isReconciliationLoading}
            onApprove={async (payment) => {
              toast.success('Match approved', {
                description: `${payment.vendor_name} matched to ${payment.matched_obligation_name}`,
              });
            }}
            onReject={async (payment) => {
              toast.success('Match rejected', {
                description: `${payment.vendor_name} will need manual matching`,
              });
            }}
            onEdit={(_payment) => {
              toast.info('Edit match', {
                description: 'Manual match editing coming soon',
              });
            }}
            onViewDetails={(payment) => {
              toast.info('Transaction details', {
                description: `Viewing ${payment.vendor_name} - ${payment.reference}`,
              });
            }}
          />
        </TabsContent>

        {/* Reconciliation Queue Tab */}
        <TabsContent value="reconciliation" className="space-y-6">
          {/* Queue Summary Bar */}
          {queueSummary && (
            <div className="rounded-xl border border-white/50 bg-white/40 backdrop-blur-sm p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gunmetal">{queueSummary.total_pending}</p>
                    <p className="text-xs text-gray-500">Pending Review</p>
                  </div>
                  <Separator orientation="vertical" className="h-10" />
                  <div className="text-center">
                    <p className="text-2xl font-bold text-mimi-pink">{queueSummary.ai_suggestions}</p>
                    <p className="text-xs text-gray-500">AI Suggestions</p>
                  </div>
                  <Separator orientation="vertical" className="h-10" />
                  <div className="text-center">
                    <p className="text-2xl font-bold text-amber-600">{queueSummary.needs_manual_match}</p>
                    <p className="text-xs text-gray-500">Need Manual Match</p>
                  </div>
                  <Separator orientation="vertical" className="h-10" />
                  <div className="text-center">
                    <p className="text-2xl font-bold text-lime-dark">{queueSummary.recently_auto_approved}</p>
                    <p className="text-xs text-gray-500">Auto-Approved (24h)</p>
                  </div>
                </div>
                {queueSummary.affecting_forecast > 0 && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-tomato/10 text-tomato">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-sm font-medium">
                      {queueSummary.affecting_forecast} item{queueSummary.affecting_forecast !== 1 ? 's' : ''} affecting forecast accuracy
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {isReconciliationLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-48 w-full rounded-xl" />
              ))}
            </div>
          ) : reconciliationSuggestions.length === 0 ? (
            <NeuroCard>
              <NeuroCardContent className="py-12">
                <div className="text-center">
                  <Sparkles className="h-12 w-12 mx-auto text-lime-dark mb-4" />
                  <h3 className="text-lg font-semibold text-gunmetal mb-2">
                    All caught up!
                  </h3>
                  <p className="text-sm text-gray-500 max-w-md mx-auto">
                    All transactions have been reconciled. New items will appear here when
                    they need your review.
                  </p>
                </div>
              </NeuroCardContent>
            </NeuroCard>
          ) : (
            <>
              {/* AI Suggestions Section */}
              {reconciliationSuggestions.filter(s => s.confidence >= 0.70).length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-mimi-pink" />
                    <h2 className="text-lg font-semibold text-gunmetal">
                      AI Suggestions
                    </h2>
                    <Badge variant="outline" className="ml-2">
                      {reconciliationSuggestions.filter(s => s.confidence >= 0.70).length} items
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-500">
                    These transactions have been matched by AI with 70%+ confidence. Review and approve or reject.
                  </p>
                  <div className="grid gap-4">
                    {reconciliationSuggestions
                      .filter(s => s.confidence >= 0.70)
                      .sort((a, b) => b.confidence - a.confidence)
                      .map((suggestion) => (
                        <ReconciliationSuggestionCard
                          key={suggestion.id}
                          suggestion={suggestion}
                          onApprove={handleApproveReconciliation}
                          onEdit={handleEditReconciliation}
                          onReject={handleRejectReconciliation}
                        />
                      ))}
                  </div>
                </div>
              )}

              {/* Needs Manual Match Section */}
              {reconciliationSuggestions.filter(s => s.confidence < 0.70).length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                    <h2 className="text-lg font-semibold text-gunmetal">
                      Needs Manual Review
                    </h2>
                    <Badge variant="outline" className="ml-2 border-amber-500 text-amber-600">
                      {reconciliationSuggestions.filter(s => s.confidence < 0.70).length} items
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-500">
                    These transactions have low confidence matches or no matches found. Manual review required.
                  </p>
                  <div className="grid gap-4">
                    {reconciliationSuggestions
                      .filter(s => s.confidence < 0.70)
                      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                      .map((suggestion) => (
                        <ReconciliationSuggestionCard
                          key={suggestion.id}
                          suggestion={suggestion}
                          onApprove={handleApproveReconciliation}
                          onEdit={handleEditReconciliation}
                          onReject={handleRejectReconciliation}
                        />
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </TabsContent>

        {/* Projections Tab - Future Data */}
        <TabsContent value="projections" className="space-y-4">
          {!forecast ? (
            <NeuroCard>
              <NeuroCardContent>
                <div className="text-center py-8 text-muted-foreground">
                  No forecast data available. Add clients and expenses to generate cash flow projections.
                </div>
              </NeuroCardContent>
            </NeuroCard>
          ) : (
            <>
              {/* 13-Week Cash Flow Overview Table */}
              <NeuroCard className="p-0 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[#f5f0eb]">
                        <th className="text-left py-3 px-4 font-medium text-muted-foreground sticky left-0 bg-[#f5f0eb] min-w-[180px]"></th>
                        {forecast.weeks.slice(0, 9).map((_, idx) => (
                          <th key={idx} className="text-center py-3 px-3 font-medium text-muted-foreground min-w-[80px]">
                            W{idx}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {/* Starting Balance */}
                      <tr className="border-b border-muted/30">
                        <td className="py-3 px-4 font-semibold sticky left-0 bg-[#f5f0eb]">Starting balance</td>
                        {forecast.weeks.slice(0, 9).map((week, idx) => (
                          <td key={idx} className="py-3 px-3 text-center font-semibold">
                            {formatCurrency(week.starting_balance)}
                          </td>
                        ))}
                      </tr>

                      {/* Income Section Header */}
                      <tr className="border-b border-muted/30">
                        <td className="py-3 px-4 sticky left-0 bg-[#f5f0eb]">
                          <div className="flex items-center gap-2">
                            <span className="text-lime-600 font-medium">↗ Income</span>
                            <span className="text-muted-foreground">^</span>
                          </div>
                        </td>
                        {forecast.weeks.slice(0, 9).map((week, idx) => (
                          <td key={idx} className="py-3 px-3 text-center text-lime-600 font-medium">
                            {parseFloat(week.cash_in) > 0 ? formatCurrency(week.cash_in) : '$0'}
                          </td>
                        ))}
                      </tr>

                      {/* Income Breakdown by Client - with links */}
                      {(() => {
                        // Get unique income sources across all weeks with source_id
                        const incomeSources = new Map<string, { weekAmounts: Map<number, number>; sourceId?: string }>();
                        forecast.weeks.slice(0, 9).forEach((week, weekIdx) => {
                          week.events
                            .filter((e) => e.direction === 'in')
                            .forEach((event) => {
                              const name = event.source_name || event.event_type;
                              if (!incomeSources.has(name)) {
                                incomeSources.set(name, { weekAmounts: new Map(), sourceId: event.source_id });
                              }
                              const current = incomeSources.get(name)!.weekAmounts.get(weekIdx) || 0;
                              incomeSources.get(name)!.weekAmounts.set(weekIdx, current + parseFloat(event.amount));
                            });
                        });

                        return Array.from(incomeSources.entries()).map(([name, { weekAmounts, sourceId }]) => {
                          const matchingClient = clients.find((c) => c.name === name || c.id === sourceId);
                          const handleClick = matchingClient
                            ? () => {
                                handleOpenClientDialog(matchingClient, true);
                              }
                            : undefined;

                          return (
                            <tr key={name} className="border-b border-muted/20">
                              <td className="py-2 px-4 pl-8 text-sm sticky left-0 bg-[#f5f0eb]">
                                <span
                                  className={`${matchingClient ? 'text-blue-600 hover:underline cursor-pointer' : 'text-muted-foreground'}`}
                                  onClick={handleClick}
                                >
                                  + {name}
                                </span>
                              </td>
                              {forecast.weeks.slice(0, 9).map((_, idx) => (
                                <td key={idx} className="py-2 px-3 text-center text-sm text-lime-600">
                                  {weekAmounts.has(idx) ? formatCurrency(weekAmounts.get(idx)!) : '$0'}
                                </td>
                              ))}
                            </tr>
                          );
                        });
                      })()}

                      {/* Costs Section Header */}
                      <tr className="border-b border-muted/30">
                        <td className="py-3 px-4 sticky left-0 bg-[#f5f0eb]">
                          <div className="flex items-center gap-2">
                            <span className="text-tomato font-medium">↙ Costs</span>
                            <span className="text-muted-foreground">^</span>
                          </div>
                        </td>
                        {forecast.weeks.slice(0, 9).map((week, idx) => (
                          <td key={idx} className="py-3 px-3 text-center text-tomato font-medium">
                            {parseFloat(week.cash_out) > 0 ? formatCurrency(week.cash_out) : '$0'}
                          </td>
                        ))}
                      </tr>

                      {/* Costs Breakdown by Category - with links */}
                      {(() => {
                        // Get unique expense categories across all weeks
                        const expenseCategories = new Map<string, { weekAmounts: Map<number, number>; sourceId?: string; sourceName?: string }>();
                        forecast.weeks.slice(0, 9).forEach((week, weekIdx) => {
                          week.events
                            .filter((e) => e.direction === 'out')
                            .forEach((event) => {
                              const category = event.category || event.source_name || event.event_type;
                              if (!expenseCategories.has(category)) {
                                expenseCategories.set(category, { weekAmounts: new Map(), sourceId: event.source_id, sourceName: event.source_name });
                              }
                              const current = expenseCategories.get(category)!.weekAmounts.get(weekIdx) || 0;
                              expenseCategories.get(category)!.weekAmounts.set(weekIdx, current + parseFloat(event.amount));
                            });
                        });

                        return Array.from(expenseCategories.entries()).map(([category, { weekAmounts, sourceId, sourceName }]) => {
                          const matchingExpense = expenses.find((e) => e.name === sourceName || e.id === sourceId || e.category === category);
                          const handleClick = matchingExpense
                            ? () => {
                                handleOpenExpenseDialog(matchingExpense, true);
                              }
                            : undefined;

                          return (
                            <tr key={category} className="border-b border-muted/20">
                              <td className="py-2 px-4 pl-8 text-sm sticky left-0 bg-[#f5f0eb] capitalize">
                                <span
                                  className={`${matchingExpense ? 'text-blue-600 hover:underline cursor-pointer' : 'text-muted-foreground'}`}
                                  onClick={handleClick}
                                >
                                  - {category}
                                </span>
                              </td>
                              {forecast.weeks.slice(0, 9).map((_, idx) => (
                                <td key={idx} className="py-2 px-3 text-center text-sm text-tomato">
                                  {weekAmounts.has(idx) ? formatCurrency(weekAmounts.get(idx)!) : '$0'}
                                </td>
                              ))}
                            </tr>
                          );
                        });
                      })()}

                      {/* Ending Balance */}
                      <tr className="bg-[#f5f0eb]">
                        <td className="py-3 px-4 font-semibold sticky left-0 bg-[#f5f0eb]">Ending balance</td>
                        {forecast.weeks.slice(0, 9).map((week, idx) => (
                          <td
                            key={idx}
                            className={`py-3 px-3 text-center font-semibold ${
                              parseFloat(week.ending_balance) < 0 ? 'text-tomato' : 'text-lime-600'
                            }`}
                          >
                            {formatCurrency(week.ending_balance)}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </NeuroCard>

              {/* Projected Transactions */}
              <NeuroCard>
                <NeuroCardHeader>
                  <NeuroCardTitle>Projected Transactions</NeuroCardTitle>
                </NeuroCardHeader>
                <NeuroCardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-3 px-4 font-semibold text-sm text-muted-foreground">Date</th>
                          <th className="text-left py-3 px-4 font-semibold text-sm text-muted-foreground">Description</th>
                          <th className="text-left py-3 px-4 font-semibold text-sm text-muted-foreground">Category</th>
                          <th className="text-right py-3 px-4 font-semibold text-sm text-muted-foreground">Amount</th>
                          <th className="text-center py-3 px-4 font-semibold text-sm text-muted-foreground">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {/* Filter for future transactions (today and after) */}
                        {forecast.weeks
                          .flatMap((week) => week.events)
                          .filter((event) => new Date(event.date) >= new Date())
                          .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
                          .map((event: ForecastEventSummary) => {
                            // Find matching client or expense
                            const matchingClient = event.direction === 'in'
                              ? clients.find((c) => c.name === event.source_name || c.id === event.source_id)
                              : null;
                            const matchingExpense = event.direction === 'out'
                              ? expenses.find((e) => e.name === event.source_name || e.id === event.source_id || e.category === event.category)
                              : null;

                            const handleClick = () => {
                              if (matchingClient) {
                                handleOpenClientDialog(matchingClient, true);
                              } else if (matchingExpense) {
                                handleOpenExpenseDialog(matchingExpense, true);
                              }
                            };

                            const isClickable = matchingClient || matchingExpense;

                            return (
                              <tr
                                key={event.id}
                                className={`border-b border-muted/50 hover:bg-muted/30 transition-colors ${isClickable ? 'cursor-pointer' : ''}`}
                                onClick={isClickable ? handleClick : undefined}
                              >
                                <td className="py-3 px-4 text-sm">
                                  {new Date(event.date).toLocaleDateString('en-US', {
                                    month: 'short',
                                    day: 'numeric',
                                    year: 'numeric',
                                  })}
                                </td>
                                <td className="py-3 px-4">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`w-2 h-2 rounded-full ${
                                        event.direction === 'in' ? 'bg-lime-500' : 'bg-tomato'
                                      }`}
                                    />
                                    <span className={`text-sm font-medium ${isClickable ? 'text-blue-600 hover:underline' : ''}`}>
                                      {event.source_name || event.event_type}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-3 px-4">
                                  <Badge variant="outline" className="text-xs capitalize">
                                    {event.category || event.event_type}
                                  </Badge>
                                </td>
                                <td
                                  className={`py-3 px-4 text-sm font-medium text-right ${
                                    event.direction === 'in' ? 'text-lime-600' : 'text-tomato'
                                  }`}
                                >
                                  {event.direction === 'in' ? '+' : '-'}
                                  {formatCurrency(event.amount)}
                                </td>
                                <td className="py-3 px-4 text-center">
                                  <Badge
                                    variant="outline"
                                    className={`text-xs ${
                                      event.confidence === 'high'
                                        ? 'border-lime-500 text-lime-600 bg-lime-50'
                                        : event.confidence === 'medium'
                                        ? 'border-yellow-500 text-yellow-600 bg-yellow-50'
                                        : 'border-gray-300 text-gray-500 bg-gray-50'
                                    }`}
                                  >
                                    {event.confidence}
                                  </Badge>
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                    {forecast.weeks.flatMap((w) => w.events).filter((e) => new Date(e.date) >= new Date()).length === 0 && (
                      <div className="text-center py-8 text-muted-foreground">
                        No projected transactions found.
                      </div>
                    )}
                  </div>
                </NeuroCardContent>
              </NeuroCard>
            </>
          )}
        </TabsContent>
      </Tabs>

      {/* Client View/Edit Dialog */}
      <Dialog open={isClientDialogOpen && !!editingClient} onOpenChange={setIsClientDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader className="flex flex-row items-start justify-between">
            <div>
              <DialogTitle>{isClientViewMode ? 'Client Details' : 'Edit Client'}</DialogTitle>
              <DialogDescription>
                {isClientViewMode ? 'View client information and billing details' : 'Update client information and billing details'}
              </DialogDescription>
            </div>
            {isClientViewMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsClientViewMode(false)}
                className="ml-auto"
              >
                <Pencil className="h-4 w-4 mr-2" />
                Edit
              </Button>
            )}
          </DialogHeader>

          {isClientViewMode ? (
            /* View Mode */
            <div className="space-y-6">
              {/* Core Client Information */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-muted-foreground">Core Information</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Client Name</Label>
                    <p className="font-medium">{clientForm.name}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Client Type</Label>
                    <p className="font-medium capitalize">{clientForm.client_type}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Currency</Label>
                    <p className="font-medium">{clientForm.currency}</p>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Status</Label>
                    <Badge variant={clientForm.status === 'active' ? 'default' : 'secondary'} className="capitalize">
                      {clientForm.status}
                    </Badge>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Risk Indicators */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-muted-foreground">Risk Indicators</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Payment Behavior</Label>
                    <Badge
                      variant="outline"
                      className={`capitalize ${
                        clientForm.payment_behavior === 'delayed' ? 'border-tomato text-tomato' :
                        clientForm.payment_behavior === 'on_time' ? 'border-lime-600 text-lime-600' : ''
                      }`}
                    >
                      {clientForm.payment_behavior.replace('_', ' ')}
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Churn Risk</Label>
                    <Badge
                      variant="outline"
                      className={`capitalize ${
                        clientForm.churn_risk === 'high' ? 'border-tomato text-tomato' :
                        clientForm.churn_risk === 'medium' ? 'border-yellow-500 text-yellow-600' :
                        'border-lime-600 text-lime-600'
                      }`}
                    >
                      {clientForm.churn_risk}
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Scope Risk</Label>
                    <Badge
                      variant="outline"
                      className={`capitalize ${
                        clientForm.scope_risk === 'high' ? 'border-tomato text-tomato' :
                        clientForm.scope_risk === 'medium' ? 'border-yellow-500 text-yellow-600' :
                        'border-lime-600 text-lime-600'
                      }`}
                    >
                      {clientForm.scope_risk}
                    </Badge>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Billing Structure */}
              <div className="space-y-4">
                <h4 className="text-sm font-medium text-muted-foreground">
                  Billing Structure
                  <span className="ml-2 text-xs font-normal">
                    ({clientForm.client_type === 'retainer' && 'Recurring Revenue'}
                    {clientForm.client_type === 'project' && 'Fixed-scope / Milestone'}
                    {clientForm.client_type === 'usage' && 'Variable / Consumption'}
                    {clientForm.client_type === 'mixed' && 'Combined Billing'})
                  </span>
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">
                      {clientForm.client_type === 'project' ? 'Total Project Value' :
                       clientForm.client_type === 'usage' ? 'Typical Amount' : 'Amount'}
                    </Label>
                    <p className="font-medium text-lg">{formatCurrency(clientForm.amount || 0)}</p>
                  </div>
                  {clientForm.client_type !== 'project' && (
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Frequency</Label>
                      <p className="font-medium capitalize">{clientForm.frequency}</p>
                    </div>
                  )}
                  {(clientForm.client_type === 'retainer' || clientForm.client_type === 'mixed') && (
                    <div className="space-y-1">
                      <Label className="text-xs text-muted-foreground">Billing Day</Label>
                      <p className="font-medium">{clientForm.day_of_month}{['1','21','31'].includes(clientForm.day_of_month) ? 'st' : ['2','22'].includes(clientForm.day_of_month) ? 'nd' : ['3','23'].includes(clientForm.day_of_month) ? 'rd' : 'th'} of month</p>
                    </div>
                  )}
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Payment Terms</Label>
                    <p className="font-medium capitalize">{clientForm.payment_terms.replace('_', ' ')}</p>
                  </div>
                </div>

                {/* Milestones for project clients */}
                {clientForm.client_type === 'project' && clientForm.milestones.length > 0 && (
                  <div className="space-y-2 mt-4">
                    <Label className="text-xs text-muted-foreground">Payment Milestones</Label>
                    <div className="space-y-2">
                      {clientForm.milestones.map((milestone, index) => (
                        <div key={index} className="flex items-center justify-between p-3 border rounded-md bg-muted/30">
                          <div>
                            <p className="font-medium">{milestone.name || `Milestone ${index + 1}`}</p>
                            <p className="text-xs text-muted-foreground">
                              {milestone.expected_date ? new Date(milestone.expected_date).toLocaleDateString() : 'Date TBD'} - {milestone.trigger_type === 'date_based' ? 'Date-based' : 'Delivery-based'}
                            </p>
                          </div>
                          <p className="font-semibold">{formatCurrency(milestone.amount || 0)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {clientForm.notes && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Notes</Label>
                    <p className="text-sm">{clientForm.notes}</p>
                  </div>
                </>
              )}
            </div>
          ) : (
            /* Edit Mode */
            <div className="space-y-6">
            {/* Core Client Information */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-muted-foreground">Core Information</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Client Name</Label>
                  <Input
                    value={clientForm.name}
                    onChange={(e) => setClientForm({ ...clientForm, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Client Type</Label>
                  <Select
                    value={clientForm.client_type}
                    onValueChange={(v: ClientType) =>
                      setClientForm({ ...clientForm, client_type: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="retainer">Retainer</SelectItem>
                      <SelectItem value="project">Project</SelectItem>
                      <SelectItem value="usage">Usage-based</SelectItem>
                      <SelectItem value="mixed">Mixed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Currency</Label>
                  <Select
                    value={clientForm.currency}
                    onValueChange={(v: Currency) =>
                      setClientForm({ ...clientForm, currency: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                      <SelectItem value="GBP">GBP</SelectItem>
                      <SelectItem value="AUD">AUD</SelectItem>
                      <SelectItem value="CAD">CAD</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select
                    value={clientForm.status}
                    onValueChange={(v: ClientStatus) =>
                      setClientForm({ ...clientForm, status: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="paused">Paused</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <Separator />

            {/* Risk Indicators */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-muted-foreground">Risk Indicators</h4>
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Payment Behavior</Label>
                  <Select
                    value={clientForm.payment_behavior}
                    onValueChange={(v: PaymentBehavior) =>
                      setClientForm({ ...clientForm, payment_behavior: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="on_time">On Time</SelectItem>
                      <SelectItem value="delayed">Delayed</SelectItem>
                      <SelectItem value="unknown">Unknown</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Churn Risk</Label>
                  <Select
                    value={clientForm.churn_risk}
                    onValueChange={(v: RiskLevel) =>
                      setClientForm({ ...clientForm, churn_risk: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Scope Risk</Label>
                  <Select
                    value={clientForm.scope_risk}
                    onValueChange={(v: RiskLevel) =>
                      setClientForm({ ...clientForm, scope_risk: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <Separator />

            {/* Billing Structure - Adaptive by Client Type */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-muted-foreground">
                Billing Structure
                <span className="ml-2 text-xs font-normal">
                  ({clientForm.client_type === 'retainer' && 'Recurring Revenue'}
                  {clientForm.client_type === 'project' && 'Fixed-scope / Milestone'}
                  {clientForm.client_type === 'usage' && 'Variable / Consumption'}
                  {clientForm.client_type === 'mixed' && 'Combined Billing'})
                </span>
              </h4>

              {/* Retainer Fields */}
              {clientForm.client_type === 'retainer' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Retainer Amount</Label>
                    <Input
                      type="number"
                      placeholder="0"
                      value={clientForm.amount}
                      onChange={(e) => setClientForm({ ...clientForm, amount: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Billing Frequency</Label>
                    <Select
                      value={clientForm.frequency}
                      onValueChange={(v: Frequency) =>
                        setClientForm({ ...clientForm, frequency: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="monthly">Monthly</SelectItem>
                        <SelectItem value="quarterly">Quarterly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Billing Day</Label>
                    <Input
                      type="number"
                      min="1"
                      max="28"
                      placeholder="1"
                      value={clientForm.day_of_month}
                      onChange={(e) => setClientForm({ ...clientForm, day_of_month: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Payment Terms</Label>
                    <Select
                      value={clientForm.payment_terms}
                      onValueChange={(v) =>
                        setClientForm({ ...clientForm, payment_terms: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="net_7">Net 7</SelectItem>
                        <SelectItem value="net_14">Net 14</SelectItem>
                        <SelectItem value="net_30">Net 30</SelectItem>
                        <SelectItem value="net_60">Net 60</SelectItem>
                        <SelectItem value="due_on_receipt">Due on Receipt</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              {/* Project Fields */}
              {clientForm.client_type === 'project' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Total Project Value</Label>
                      <Input
                        type="number"
                        placeholder="0"
                        value={clientForm.total_project_value || clientForm.amount}
                        onChange={(e) => setClientForm({ ...clientForm, total_project_value: e.target.value, amount: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Payment Terms</Label>
                      <Select
                        value={clientForm.payment_terms}
                        onValueChange={(v) =>
                          setClientForm({ ...clientForm, payment_terms: v })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="net_7">Net 7</SelectItem>
                          <SelectItem value="net_14">Net 14</SelectItem>
                          <SelectItem value="net_30">Net 30</SelectItem>
                          <SelectItem value="net_60">Net 60</SelectItem>
                          <SelectItem value="due_on_receipt">Due on Receipt</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Milestones */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Payment Milestones</Label>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setClientForm({
                          ...clientForm,
                          milestones: [...clientForm.milestones, {
                            name: '',
                            amount: '',
                            expected_date: '',
                            trigger_type: 'date_based'
                          }]
                        })}
                      >
                        <Plus className="h-4 w-4 mr-1" />
                        Add Milestone
                      </Button>
                    </div>
                    {clientForm.milestones.map((milestone, index) => (
                      <div key={index} className="grid grid-cols-4 gap-2 p-3 border rounded-md bg-muted/30">
                        <div className="space-y-1">
                          <Label className="text-xs">Name</Label>
                          <Input
                            placeholder="e.g., Deposit"
                            value={milestone.name}
                            onChange={(e) => {
                              const updated = [...clientForm.milestones];
                              updated[index] = { ...updated[index], name: e.target.value };
                              setClientForm({ ...clientForm, milestones: updated });
                            }}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Amount</Label>
                          <Input
                            type="number"
                            placeholder="0"
                            value={milestone.amount}
                            onChange={(e) => {
                              const updated = [...clientForm.milestones];
                              updated[index] = { ...updated[index], amount: e.target.value };
                              setClientForm({ ...clientForm, milestones: updated });
                            }}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Expected Date</Label>
                          <Input
                            type="date"
                            value={milestone.expected_date}
                            onChange={(e) => {
                              const updated = [...clientForm.milestones];
                              updated[index] = { ...updated[index], expected_date: e.target.value };
                              setClientForm({ ...clientForm, milestones: updated });
                            }}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Trigger</Label>
                          <div className="flex gap-1">
                            <Select
                              value={milestone.trigger_type}
                              onValueChange={(v: 'date_based' | 'delivery_based') => {
                                const updated = [...clientForm.milestones];
                                updated[index] = { ...updated[index], trigger_type: v };
                                setClientForm({ ...clientForm, milestones: updated });
                              }}
                            >
                              <SelectTrigger className="flex-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="date_based">Date</SelectItem>
                                <SelectItem value="delivery_based">Delivery</SelectItem>
                              </SelectContent>
                            </Select>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-9 w-9 shrink-0"
                              onClick={() => {
                                const updated = clientForm.milestones.filter((_, i) => i !== index);
                                setClientForm({ ...clientForm, milestones: updated });
                              }}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                    {clientForm.milestones.length === 0 && (
                      <p className="text-sm text-muted-foreground italic">No milestones added. Click "Add Milestone" to create payment schedule.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Usage-based Fields */}
              {clientForm.client_type === 'usage' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Typical Settlement Amount</Label>
                    <Input
                      type="number"
                      placeholder="Estimate or average"
                      value={clientForm.typical_amount || clientForm.amount}
                      onChange={(e) => setClientForm({ ...clientForm, typical_amount: e.target.value, amount: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Settlement Frequency</Label>
                    <Select
                      value={clientForm.frequency}
                      onValueChange={(v: Frequency) =>
                        setClientForm({ ...clientForm, frequency: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="weekly">Weekly</SelectItem>
                        <SelectItem value="bi_weekly">Bi-weekly</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Payment Terms</Label>
                    <Select
                      value={clientForm.payment_terms}
                      onValueChange={(v) =>
                        setClientForm({ ...clientForm, payment_terms: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="net_7">Net 7</SelectItem>
                        <SelectItem value="net_14">Net 14</SelectItem>
                        <SelectItem value="net_30">Net 30</SelectItem>
                        <SelectItem value="due_on_receipt">Due on Receipt</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              {/* Mixed Revenue Fields */}
              {clientForm.client_type === 'mixed' && (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Mixed revenue clients combine multiple billing models. Configure the primary billing amount below.
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Primary Amount</Label>
                      <Input
                        type="number"
                        placeholder="0"
                        value={clientForm.amount}
                        onChange={(e) => setClientForm({ ...clientForm, amount: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Primary Frequency</Label>
                      <Select
                        value={clientForm.frequency}
                        onValueChange={(v: Frequency) =>
                          setClientForm({ ...clientForm, frequency: v })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="weekly">Weekly</SelectItem>
                          <SelectItem value="monthly">Monthly</SelectItem>
                          <SelectItem value="quarterly">Quarterly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Billing Day</Label>
                      <Input
                        type="number"
                        min="1"
                        max="28"
                        placeholder="1"
                        value={clientForm.day_of_month}
                        onChange={(e) => setClientForm({ ...clientForm, day_of_month: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Payment Terms</Label>
                      <Select
                        value={clientForm.payment_terms}
                        onValueChange={(v) =>
                          setClientForm({ ...clientForm, payment_terms: v })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="net_7">Net 7</SelectItem>
                          <SelectItem value="net_14">Net 14</SelectItem>
                          <SelectItem value="net_30">Net 30</SelectItem>
                          <SelectItem value="net_60">Net 60</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <Separator />

            {/* Notes */}
            <div className="space-y-2">
              <Label>Notes (optional)</Label>
              <Input
                placeholder="Additional notes about this client..."
                value={clientForm.notes}
                onChange={(e) => setClientForm({ ...clientForm, notes: e.target.value })}
              />
            </div>

            <Button className="w-full" onClick={handleSaveClient}>
              Save Changes
            </Button>
          </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Expense View/Edit Dialog */}
      <Dialog open={isExpenseDialogOpen && !!editingExpense} onOpenChange={setIsExpenseDialogOpen}>
        <DialogContent>
          <DialogHeader className="flex flex-row items-start justify-between">
            <div>
              <DialogTitle>{isExpenseViewMode ? 'Expense Details' : 'Edit Expense'}</DialogTitle>
              <DialogDescription>
                {isExpenseViewMode ? 'View expense information' : 'Update expense information'}
              </DialogDescription>
            </div>
            {isExpenseViewMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsExpenseViewMode(false)}
                className="ml-auto"
              >
                <Pencil className="h-4 w-4 mr-2" />
                Edit
              </Button>
            )}
          </DialogHeader>

          {isExpenseViewMode ? (
            /* View Mode */
            <div className="space-y-4">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Name</Label>
                <p className="font-medium text-lg">{expenseForm.name}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Monthly Amount</Label>
                  <p className="font-medium text-lg">{formatCurrency(expenseForm.monthly_amount)}</p>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Category</Label>
                  <Badge variant="outline" className="capitalize">{expenseForm.category}</Badge>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Type</Label>
                  <Badge variant={expenseForm.bucket_type === 'fixed' ? 'secondary' : 'outline'} className="capitalize">
                    {expenseForm.bucket_type}
                  </Badge>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Priority</Label>
                  <Badge
                    variant="outline"
                    className={`capitalize ${
                      expenseForm.priority === 'essential' ? 'border-tomato text-tomato' :
                      expenseForm.priority === 'important' ? 'border-yellow-500 text-yellow-600' :
                      'border-gray-300 text-gray-500'
                    }`}
                  >
                    {expenseForm.priority}
                  </Badge>
                </div>
                {expenseForm.employee_count && (
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Number of Employees</Label>
                    <p className="font-medium">{expenseForm.employee_count}</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* Edit Mode */
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={expenseForm.name}
                  onChange={(e) => setExpenseForm({ ...expenseForm, name: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Monthly Amount</Label>
                  <Input
                    type="number"
                    value={expenseForm.monthly_amount}
                    onChange={(e) =>
                      setExpenseForm({ ...expenseForm, monthly_amount: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select
                    value={expenseForm.priority}
                    onValueChange={(v: Priority) =>
                      setExpenseForm({ ...expenseForm, priority: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="essential">Essential</SelectItem>
                      <SelectItem value="important">Important</SelectItem>
                      <SelectItem value="discretionary">Discretionary</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button className="w-full" onClick={handleSaveExpense}>
                Save Changes
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Xero Sync Success Dialog */}
      <Dialog open={xeroSyncDialog.isOpen} onOpenChange={(open) => setXeroSyncDialog({ ...xeroSyncDialog, isOpen: open })}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <DialogTitle className="text-xl">
                {xeroSyncDialog.type === 'client' ? 'Client' : 'Expense'} Added Successfully
              </DialogTitle>
            </div>
            <DialogDescription className="text-base pt-2">
              <span className="font-semibold text-foreground">{xeroSyncDialog.name}</span> has been synced to Xero.
            </DialogDescription>
          </DialogHeader>

          <div className="bg-muted/50 rounded-lg p-4 my-4">
            <p className="text-sm text-muted-foreground">
              {xeroSyncDialog.type === 'client' ? (
                <>
                  Create your first invoice in Xero to strengthen revenue certainty.
                  Once invoiced, this client will appear in your Xero Customers list and
                  payment tracking becomes automatic.
                </>
              ) : (
                <>
                  Create a bill in Xero to track this expense accurately.
                  Once billed, this supplier will appear in your Xero Suppliers list and
                  expense tracking becomes automatic.
                </>
              )}
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <Button
              className="w-full"
              onClick={() => {
                const url = xeroSyncDialog.type === 'client'
                  ? 'https://go.xero.com/app/invoicing/edit'
                  : 'https://go.xero.com/AccountsPayable/Edit.aspx';
                window.open(url, '_blank');
                setXeroSyncDialog({ ...xeroSyncDialog, isOpen: false });
              }}
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              {xeroSyncDialog.type === 'client' ? 'Create Invoice in Xero' : 'Create Bill in Xero'}
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => setXeroSyncDialog({ ...xeroSyncDialog, isOpen: false })}
            >
              I'll do this later
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
