import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NeuroCard, NeuroCardContent, NeuroCardDescription, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Plus, Trash2, ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { createCashPosition, createClient, createExpense } from '@/lib/api/data';
import type {
  ClientType,
  PaymentBehavior,
  RiskLevel,
  ExpenseCategory,
  BucketType,
  Priority,
  Frequency,
} from '@/lib/api/types';

type OnboardingStep = 'cash' | 'clients' | 'expenses' | 'buffer' | 'loading';

interface CashAccountForm {
  account_name: string;
  balance: string;
  currency: string;
}

interface ClientForm {
  name: string;
  client_type: ClientType;
  amount: string;
  frequency: Frequency;
  payment_behavior: PaymentBehavior;
  churn_risk: RiskLevel;
}

interface ExpenseForm {
  name: string;
  category: ExpenseCategory;
  bucket_type: BucketType;
  monthly_amount: string;
  priority: Priority;
  employee_count?: string;
}

export default function OnboardingManual() {
  const navigate = useNavigate();
  const { user, completeOnboarding } = useAuth();
  const [step, setStep] = useState<OnboardingStep>('cash');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Cash Position State
  const [accounts, setAccounts] = useState<CashAccountForm[]>([
    { account_name: 'Main Business Account', balance: '', currency: 'USD' },
  ]);

  // Clients State
  const [clients, setClients] = useState<ClientForm[]>([]);

  // Expenses State
  const [expenses, setExpenses] = useState<ExpenseForm[]>([]);

  // Buffer Rule State
  const [bufferMonths, setBufferMonths] = useState('3');

  const addAccount = () => {
    setAccounts([...accounts, { account_name: '', balance: '', currency: 'USD' }]);
  };

  const removeAccount = (index: number) => {
    setAccounts(accounts.filter((_, i) => i !== index));
  };

  const updateAccount = (index: number, field: keyof CashAccountForm, value: string) => {
    const updated = [...accounts];
    updated[index][field] = value;
    setAccounts(updated);
  };

  const addClient = () => {
    setClients([
      ...clients,
      {
        name: '',
        client_type: 'retainer',
        amount: '',
        frequency: 'monthly',
        payment_behavior: 'on_time',
        churn_risk: 'low',
      },
    ]);
  };

  const removeClient = (index: number) => {
    setClients(clients.filter((_, i) => i !== index));
  };

  const updateClient = (index: number, field: keyof ClientForm, value: string) => {
    const updated = [...clients];
    updated[index] = { ...updated[index], [field]: value };
    setClients(updated);
  };

  const addExpense = () => {
    setExpenses([
      ...expenses,
      {
        name: '',
        category: 'other',
        bucket_type: 'fixed',
        monthly_amount: '',
        priority: 'medium',
      },
    ]);
  };

  const removeExpense = (index: number) => {
    setExpenses(expenses.filter((_, i) => i !== index));
  };

  const updateExpense = (index: number, field: keyof ExpenseForm, value: string) => {
    const updated = [...expenses];
    updated[index] = { ...updated[index], [field]: value };
    setExpenses(updated);
  };

  const validateStep = (): boolean => {
    setError('');

    if (step === 'cash') {
      const validAccounts = accounts.filter((a) => a.account_name && a.balance);
      if (validAccounts.length === 0) {
        setError('Please add at least one account with a balance');
        return false;
      }
    }

    return true;
  };

  const handleNext = () => {
    if (!validateStep()) return;

    const steps: OnboardingStep[] = ['cash', 'clients', 'expenses', 'buffer'];
    const currentIndex = steps.indexOf(step);
    if (currentIndex < steps.length - 1) {
      setStep(steps[currentIndex + 1]);
    }
  };

  const handleBack = () => {
    const steps: OnboardingStep[] = ['cash', 'clients', 'expenses', 'buffer'];
    const currentIndex = steps.indexOf(step);
    if (currentIndex > 0) {
      setStep(steps[currentIndex - 1]);
    }
  };

  const handleComplete = async () => {
    if (!user) return;
    setIsSubmitting(true);
    setStep('loading');
    setError('');

    try {
      // 1. Create cash position
      const validAccounts = accounts.filter((a) => a.account_name && a.balance);
      await createCashPosition(
        user.id,
        validAccounts.map((a) => ({
          account_name: a.account_name,
          balance: a.balance,
          currency: a.currency as 'USD',
          as_of_date: new Date().toISOString().split('T')[0],
        }))
      );

      // 2. Create clients
      for (const client of clients.filter((c) => c.name && c.amount)) {
        await createClient({
          user_id: user.id,
          name: client.name,
          client_type: client.client_type,
          currency: 'USD',
          status: 'active',
          payment_behavior: client.payment_behavior,
          churn_risk: client.churn_risk,
          scope_risk: 'low',
          billing_config: {
            amount: client.amount,
            frequency: client.frequency,
            day_of_month: 1,
          },
        });
      }

      // 3. Create expenses
      for (const expense of expenses.filter((e) => e.name && e.monthly_amount)) {
        await createExpense({
          user_id: user.id,
          name: expense.name,
          category: expense.category,
          bucket_type: expense.bucket_type,
          monthly_amount: expense.monthly_amount,
          currency: 'USD',
          priority: expense.priority,
          is_stable: expense.bucket_type === 'fixed',
          due_day: 15,
          frequency: 'monthly',
          employee_count: expense.employee_count ? parseInt(expense.employee_count) : undefined,
        });
      }

      // 4. Mark onboarding complete
      await completeOnboarding();

      // Navigate to dashboard
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete setup');
      setStep('buffer');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Progress indicator
  const steps: OnboardingStep[] = ['cash', 'clients', 'expenses', 'buffer'];
  const currentStepIndex = steps.indexOf(step);
  const progress = step === 'loading' ? 100 : ((currentStepIndex + 1) / steps.length) * 100;

  return (
    <div className="min-h-screen py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-foreground">TAMIO</h1>
          <p className="text-muted-foreground mt-2">Set up your 13-week forecast</p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-xs text-muted-foreground">
            <span className={step === 'cash' ? 'text-foreground font-medium' : ''}>
              Cash Position
            </span>
            <span className={step === 'clients' ? 'text-foreground font-medium' : ''}>
              Clients
            </span>
            <span className={step === 'expenses' ? 'text-foreground font-medium' : ''}>
              Expenses
            </span>
            <span className={step === 'buffer' ? 'text-foreground font-medium' : ''}>
              Buffer Rule
            </span>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Step: Cash Position */}
        {step === 'cash' && (
          <NeuroCard>
            <NeuroCardHeader>
              <NeuroCardTitle>What's your current cash position?</NeuroCardTitle>
              <NeuroCardDescription>
                Enter your bank account balances as of today. This is your starting point.
              </NeuroCardDescription>
            </NeuroCardHeader>
            <NeuroCardContent className="space-y-4">
              {accounts.map((account, index) => (
                <div key={index} className="flex gap-3 items-start">
                  <div className="flex-1 space-y-2">
                    <Label>Account Name</Label>
                    <Input
                      placeholder="e.g., Main Checking"
                      value={account.account_name}
                      onChange={(e) => updateAccount(index, 'account_name', e.target.value)}
                    />
                  </div>
                  <div className="w-40 space-y-2">
                    <Label>Balance</Label>
                    <Input
                      type="number"
                      placeholder="0.00"
                      value={account.balance}
                      onChange={(e) => updateAccount(index, 'balance', e.target.value)}
                    />
                  </div>
                  <div className="w-24 space-y-2">
                    <Label>Currency</Label>
                    <Select
                      value={account.currency}
                      onValueChange={(v) => updateAccount(index, 'currency', v)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="USD">USD</SelectItem>
                        <SelectItem value="EUR">EUR</SelectItem>
                        <SelectItem value="GBP">GBP</SelectItem>
                        <SelectItem value="AUD">AUD</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {accounts.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="mt-8"
                      onClick={() => removeAccount(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addAccount}>
                <Plus className="h-4 w-4 mr-2" />
                Add Another Account
              </Button>
            </NeuroCardContent>
          </NeuroCard>
        )}

        {/* Step: Clients */}
        {step === 'clients' && (
          <NeuroCard>
            <NeuroCardHeader>
              <NeuroCardTitle>Who are your clients?</NeuroCardTitle>
              <NeuroCardDescription>
                Add your revenue sources. You can add more later.
              </NeuroCardDescription>
            </NeuroCardHeader>
            <NeuroCardContent className="space-y-6">
              {clients.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No clients added yet.</p>
                  <p className="text-sm">Click below to add your first client.</p>
                </div>
              ) : (
                clients.map((client, index) => (
                  <div key={index} className="p-4 border rounded-lg space-y-4">
                    <div className="flex justify-between items-center">
                      <h4 className="font-medium">Client {index + 1}</h4>
                      <Button variant="ghost" size="sm" onClick={() => removeClient(index)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Client Name</Label>
                        <Input
                          placeholder="e.g., Acme Corp"
                          value={client.name}
                          onChange={(e) => updateClient(index, 'name', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Client Type</Label>
                        <Select
                          value={client.client_type}
                          onValueChange={(v) => updateClient(index, 'client_type', v)}
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
                        <Label>Amount</Label>
                        <Input
                          type="number"
                          placeholder="Monthly amount"
                          value={client.amount}
                          onChange={(e) => updateClient(index, 'amount', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Frequency</Label>
                        <Select
                          value={client.frequency}
                          onValueChange={(v) => updateClient(index, 'frequency', v)}
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
                        <Label>Payment Behavior</Label>
                        <Select
                          value={client.payment_behavior}
                          onValueChange={(v) => updateClient(index, 'payment_behavior', v)}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="on_time">On Time</SelectItem>
                            <SelectItem value="delayed">Often Delayed</SelectItem>
                            <SelectItem value="unknown">Unknown</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Churn Risk</Label>
                        <Select
                          value={client.churn_risk}
                          onValueChange={(v) => updateClient(index, 'churn_risk', v)}
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
                ))
              )}
              <Button variant="outline" onClick={addClient}>
                <Plus className="h-4 w-4 mr-2" />
                Add Client
              </Button>
            </NeuroCardContent>
          </NeuroCard>
        )}

        {/* Step: Expenses */}
        {step === 'expenses' && (
          <NeuroCard>
            <NeuroCardHeader>
              <NeuroCardTitle>What are your regular expenses?</NeuroCardTitle>
              <NeuroCardDescription>
                Add expense buckets for payroll, rent, contractors, tools, etc.
              </NeuroCardDescription>
            </NeuroCardHeader>
            <NeuroCardContent className="space-y-6">
              {expenses.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No expenses added yet.</p>
                  <p className="text-sm">Click below to add your first expense bucket.</p>
                </div>
              ) : (
                expenses.map((expense, index) => (
                  <div key={index} className="p-4 border rounded-lg space-y-4">
                    <div className="flex justify-between items-center">
                      <h4 className="font-medium">Expense {index + 1}</h4>
                      <Button variant="ghost" size="sm" onClick={() => removeExpense(index)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Name</Label>
                        <Input
                          placeholder="e.g., Payroll"
                          value={expense.name}
                          onChange={(e) => updateExpense(index, 'name', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Category</Label>
                        <Select
                          value={expense.category}
                          onValueChange={(v) => updateExpense(index, 'category', v)}
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
                          placeholder="0.00"
                          value={expense.monthly_amount}
                          onChange={(e) => updateExpense(index, 'monthly_amount', e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Type</Label>
                        <Select
                          value={expense.bucket_type}
                          onValueChange={(v) => updateExpense(index, 'bucket_type', v)}
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
                          value={expense.priority}
                          onValueChange={(v) => updateExpense(index, 'priority', v)}
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
                      {expense.category === 'payroll' && (
                        <div className="space-y-2">
                          <Label>Number of Employees</Label>
                          <Input
                            type="number"
                            placeholder="0"
                            value={expense.employee_count || ''}
                            onChange={(e) => updateExpense(index, 'employee_count', e.target.value)}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              <Button variant="outline" onClick={addExpense}>
                <Plus className="h-4 w-4 mr-2" />
                Add Expense Bucket
              </Button>
            </NeuroCardContent>
          </NeuroCard>
        )}

        {/* Step: Buffer Rule */}
        {step === 'buffer' && (
          <NeuroCard>
            <NeuroCardHeader>
              <NeuroCardTitle>Set your cash buffer rule</NeuroCardTitle>
              <NeuroCardDescription>
                How many months of expenses do you want to maintain as a safety buffer?
                Tamio will alert you if your forecast dips below this threshold.
              </NeuroCardDescription>
            </NeuroCardHeader>
            <NeuroCardContent className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <Label>Minimum Runway Buffer</Label>
                  <Select value={bufferMonths} onValueChange={setBufferMonths}>
                    <SelectTrigger className="mt-2">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 month</SelectItem>
                      <SelectItem value="2">2 months</SelectItem>
                      <SelectItem value="3">3 months (recommended)</SelectItem>
                      <SelectItem value="4">4 months</SelectItem>
                      <SelectItem value="6">6 months</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  This rule will be evaluated against your forecast. If any week falls below{' '}
                  <span className="font-medium text-foreground">{bufferMonths} months</span>{' '}
                  of operating expenses, you'll see a warning.
                </p>
              </div>
            </NeuroCardContent>
          </NeuroCard>
        )}

        {/* Step: Loading */}
        {step === 'loading' && (
          <NeuroCard>
            <NeuroCardContent className="py-16">
              <div className="text-center space-y-4">
                <Loader2 className="h-12 w-12 animate-spin mx-auto text-primary" />
                <h3 className="text-xl font-semibold">Building your 13-week forecast...</h3>
                <p className="text-muted-foreground">
                  This will just take a moment.
                </p>
              </div>
            </NeuroCardContent>
          </NeuroCard>
        )}

        {/* Navigation */}
        {step !== 'loading' && (
          <div className="flex justify-between mt-8">
            {step === 'cash' ? (
              <Button variant="ghost" onClick={() => navigate('/onboarding')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            ) : (
              <Button variant="outline" onClick={handleBack}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            )}

            {step === 'buffer' ? (
              <Button onClick={handleComplete} disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    Complete Setup
                    <Check className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            ) : (
              <Button onClick={handleNext}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
