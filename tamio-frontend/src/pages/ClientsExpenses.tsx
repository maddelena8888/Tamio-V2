import { useEffect, useState } from 'react';
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
import { Plus, ArrowUpDown, Trash2, ExternalLink, CheckCircle } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { getClients, createClient, updateClient, deleteClient } from '@/lib/api/data';
import { getExpenses, createExpense, updateExpense, deleteExpense } from '@/lib/api/data';
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
} from '@/lib/api/types';

interface Milestone {
  name: string;
  amount: string;
  expected_date: string;
  trigger_type: 'date_based' | 'delivery_based';
}

export default function ClientsExpenses() {
  const { user } = useAuth();
  const [clients, setClients] = useState<Client[]>([]);
  const [expenses, setExpenses] = useState<ExpenseBucket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('clients');

  // Client form state
  const [isClientDialogOpen, setIsClientDialogOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
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

  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const [clientsData, expensesData] = await Promise.all([
          getClients(user.id),
          getExpenses(user.id),
        ]);
        setClients(clientsData);
        setExpenses(expensesData);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [user]);

  // Client handlers
  const handleOpenClientDialog = (client?: Client) => {
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
  const handleOpenExpenseDialog = (expense?: ExpenseBucket) => {
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

  const formatCurrency = (value: string | number) => {
    const num = typeof value === 'string' ? parseFloat(value) : value;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
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
          return parseFloat(b.billing_config.amount || '0') - parseFloat(a.billing_config.amount || '0');
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
        <h1 className="text-2xl font-bold">Clients & Expenses</h1>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex items-center justify-between">
          <TabsList className="glass-strong !h-11 !p-1 !rounded-xl gap-1 w-fit shadow-lg shadow-black/5 !bg-white/85">
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
            <NeuroCard key={client.id} className="p-4">
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
                      {formatCurrency(client.billing_config.amount || 0)}/
                      {client.billing_config.frequency}
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
            <NeuroCard key={expense.id} className="p-4">
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
      </Tabs>

      {/* Client Edit Dialog */}
      <Dialog open={isClientDialogOpen && !!editingClient} onOpenChange={setIsClientDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Client</DialogTitle>
            <DialogDescription>Update client information and billing details</DialogDescription>
          </DialogHeader>
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
        </DialogContent>
      </Dialog>

      {/* Expense Edit Dialog */}
      <Dialog open={isExpenseDialogOpen && !!editingExpense} onOpenChange={setIsExpenseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Expense</DialogTitle>
            <DialogDescription>Update expense information</DialogDescription>
          </DialogHeader>
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
