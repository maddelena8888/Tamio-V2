import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { NeuroCard, NeuroCardContent, NeuroCardDescription, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Link2,
  Unlink,
  RefreshCw,
  Check,
  AlertTriangle,
  Settings as SettingsIcon,
  Shield,
  Loader2,
} from 'lucide-react';
import {
  getXeroStatus,
  getXeroConnectUrl,
  disconnectXero,
  syncXero,
} from '@/lib/api/xero';
import {
  getQuickBooksStatus,
  getQuickBooksConnectUrl,
  disconnectQuickBooks,
  syncQuickBooks,
  type QuickBooksConnectionStatus,
} from '@/lib/api/quickbooks';
import { getRules, createRule, updateRule } from '@/lib/api/scenarios';
import type { XeroConnectionStatus, FinancialRule } from '@/lib/api/types';

export default function Settings() {
  const { user, logout } = useAuth();
  const [xeroStatus, setXeroStatus] = useState<XeroConnectionStatus | null>(null);
  const [quickBooksStatus, setQuickBooksStatus] = useState<QuickBooksConnectionStatus | null>(null);
  const [rules, setRules] = useState<FinancialRule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isSyncingQB, setIsSyncingQB] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnectingQB, setIsConnectingQB] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [bufferMonths, setBufferMonths] = useState('3');
  const [showDisconnectDialog, setShowDisconnectDialog] = useState(false);
  const [showDisconnectQBDialog, setShowDisconnectQBDialog] = useState(false);

  useEffect(() => {
    if (!user) return;

    const fetchData = async () => {
      try {
        const [xeroData, quickBooksData, rulesData] = await Promise.all([
          getXeroStatus(user.id).catch(() => null),
          getQuickBooksStatus(user.id).catch(() => null),
          getRules(user.id).catch(() => []),
        ]);

        setXeroStatus(xeroData);
        setQuickBooksStatus(quickBooksData);
        setRules(rulesData);

        // Set buffer months from existing rule
        const bufferRule = rulesData.find((r) => r.rule_type === 'minimum_cash_buffer');
        if (bufferRule) {
          const months = (bufferRule.threshold_config as { months?: number })?.months;
          if (months) setBufferMonths(months.toString());
        }
      } catch (error) {
        console.error('Failed to fetch settings data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();

    // Check URL for Xero or QuickBooks callback
    const params = new URLSearchParams(window.location.search);
    if (params.get('xero_connected') === 'true' || params.get('quickbooks_connected') === 'true') {
      fetchData();
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [user]);

  const handleConnectXero = async () => {
    if (!user) return;
    setIsConnecting(true);
    try {
      const { auth_url } = await getXeroConnectUrl(user.id);
      window.location.href = auth_url;
    } catch (error) {
      console.error('Failed to get Xero auth URL:', error);
      setIsConnecting(false);
    }
  };

  const handleDisconnectXero = async () => {
    if (!user) return;
    try {
      await disconnectXero(user.id);
      setXeroStatus({ ...xeroStatus!, is_connected: false });
      setShowDisconnectDialog(false);
    } catch (error) {
      console.error('Failed to disconnect Xero:', error);
    }
  };

  const handleSyncXero = async () => {
    if (!user) return;
    setIsSyncing(true);
    setSyncMessage('');
    try {
      const result = await syncXero(user.id, 'full');
      setSyncMessage(
        `Xero sync complete: ${result.records_created} created, ${result.records_updated} updated`
      );
      // Refresh status
      const statusData = await getXeroStatus(user.id);
      setXeroStatus(statusData);
    } catch (error) {
      console.error('Failed to sync Xero:', error);
      setSyncMessage('Xero sync failed. Please try again.');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleConnectQuickBooks = async () => {
    if (!user) return;
    setIsConnectingQB(true);
    try {
      const { auth_url } = await getQuickBooksConnectUrl(user.id);
      window.location.href = auth_url;
    } catch (error) {
      console.error('Failed to get QuickBooks auth URL:', error);
      setIsConnectingQB(false);
    }
  };

  const handleDisconnectQuickBooks = async () => {
    if (!user) return;
    try {
      await disconnectQuickBooks(user.id);
      setQuickBooksStatus({ ...quickBooksStatus!, is_connected: false });
      setShowDisconnectQBDialog(false);
    } catch (error) {
      console.error('Failed to disconnect QuickBooks:', error);
    }
  };

  const handleSyncQuickBooks = async () => {
    if (!user) return;
    setIsSyncingQB(true);
    setSyncMessage('');
    try {
      const result = await syncQuickBooks(user.id, 'full');
      const created = Object.values(result.records_created).reduce((a, b) => a + b, 0);
      const updated = Object.values(result.records_updated).reduce((a, b) => a + b, 0);
      setSyncMessage(`QuickBooks sync complete: ${created} created, ${updated} updated`);
      // Refresh status
      const statusData = await getQuickBooksStatus(user.id);
      setQuickBooksStatus(statusData);
    } catch (error) {
      console.error('Failed to sync QuickBooks:', error);
      setSyncMessage('QuickBooks sync failed. Please try again.');
    } finally {
      setIsSyncingQB(false);
    }
  };

  const handleUpdateBufferRule = async () => {
    if (!user) return;
    try {
      const existingRule = rules.find((r) => r.rule_type === 'minimum_cash_buffer');
      if (existingRule) {
        await updateRule(existingRule.id, {
          threshold_config: { months: parseInt(bufferMonths) },
        });
      } else {
        await createRule({
          user_id: user.id,
          rule_type: 'minimum_cash_buffer',
          name: 'Minimum Cash Buffer',
          description: `Maintain at least ${bufferMonths} months of operating expenses`,
          threshold_config: { months: parseInt(bufferMonths) },
          is_active: true,
          evaluation_scope: 'all',
        });
      }
      setSyncMessage('Buffer rule updated successfully');
    } catch (error) {
      console.error('Failed to update buffer rule:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="font-league-spartan text-3xl font-bold text-gunmetal">Settings</h1>

      {syncMessage && (
        <Alert className="bg-white/60 backdrop-blur-sm border-white/30">
          <Check className="h-4 w-4" />
          <AlertDescription>{syncMessage}</AlertDescription>
        </Alert>
      )}

      {/* Xero Integration */}
      <NeuroCard>
        <NeuroCardHeader>
          <NeuroCardTitle className="flex items-center gap-2 font-league-spartan text-xl font-bold text-gunmetal">
            <div className="w-10 h-10 rounded-xl bg-white/60 backdrop-blur-sm border border-white/30 flex items-center justify-center">
              <Link2 className="h-5 w-5 text-[#13B5EA]" />
            </div>
            Xero Integration
          </NeuroCardTitle>
          <NeuroCardDescription>
            Connect your Xero account to automatically sync financial data
          </NeuroCardDescription>
        </NeuroCardHeader>
        <NeuroCardContent className="space-y-4">
          {xeroStatus?.is_connected ? (
            <>
              <div className="flex items-center justify-between p-4 bg-white/40 backdrop-blur-sm rounded-xl border border-white/20">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#13B5EA] flex items-center justify-center">
                    <Check className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="font-medium text-gunmetal">{xeroStatus.tenant_name || 'Connected'}</p>
                    <p className="text-sm text-muted-foreground">
                      Last synced:{' '}
                      {xeroStatus.last_sync_at
                        ? new Date(xeroStatus.last_sync_at).toLocaleDateString()
                        : 'Never'}
                    </p>
                  </div>
                </div>
                <Badge className="bg-lime text-gunmetal font-semibold">Connected</Badge>
              </div>

              {xeroStatus.sync_error && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{xeroStatus.sync_error}</AlertDescription>
                </Alert>
              )}

              <div className="flex gap-3">
                <Button onClick={handleSyncXero} disabled={isSyncing} className="rounded-full">
                  {isSyncing ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Sync Now
                    </>
                  )}
                </Button>
                <Dialog open={showDisconnectDialog} onOpenChange={setShowDisconnectDialog}>
                  <DialogTrigger asChild>
                    <Button variant="outline" className="rounded-full">
                      <Unlink className="mr-2 h-4 w-4" />
                      Disconnect
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Disconnect Xero</DialogTitle>
                      <DialogDescription>
                        Are you sure you want to disconnect your Xero account? Your existing data
                        will remain, but automatic syncing will stop.
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowDisconnectDialog(false)}>
                        Cancel
                      </Button>
                      <Button variant="destructive" onClick={handleDisconnectXero}>
                        Disconnect
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Connect Xero to automatically import your clients, invoices, bills, and bank
                balances.
              </p>
              <Button
                onClick={handleConnectXero}
                disabled={isConnecting}
                className="rounded-full bg-[#13B5EA] hover:bg-[#0fa3d4] text-white"
              >
                {isConnecting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <Link2 className="mr-2 h-4 w-4" />
                    Connect to Xero
                  </>
                )}
              </Button>
            </div>
          )}
        </NeuroCardContent>
      </NeuroCard>

      {/* QuickBooks Integration */}
      <NeuroCard>
        <NeuroCardHeader>
          <NeuroCardTitle className="flex items-center gap-2 font-league-spartan text-xl font-bold text-gunmetal">
            <div className="w-10 h-10 rounded-xl bg-white/60 backdrop-blur-sm border border-white/30 flex items-center justify-center">
              <Link2 className="h-5 w-5 text-[#2CA01C]" />
            </div>
            QuickBooks Integration
          </NeuroCardTitle>
          <NeuroCardDescription>
            Connect your QuickBooks Online account to automatically sync financial data
          </NeuroCardDescription>
        </NeuroCardHeader>
        <NeuroCardContent className="space-y-4">
          {quickBooksStatus?.is_connected ? (
            <>
              <div className="flex items-center justify-between p-4 bg-white/40 backdrop-blur-sm rounded-xl border border-white/20">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#2CA01C] flex items-center justify-center">
                    <Check className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="font-medium text-gunmetal">{quickBooksStatus.company_name || 'Connected'}</p>
                    <p className="text-sm text-muted-foreground">
                      Last synced:{' '}
                      {quickBooksStatus.last_sync_at
                        ? new Date(quickBooksStatus.last_sync_at).toLocaleDateString()
                        : 'Never'}
                    </p>
                  </div>
                </div>
                <Badge className="bg-lime text-gunmetal font-semibold">Connected</Badge>
              </div>

              {quickBooksStatus.sync_error && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{quickBooksStatus.sync_error}</AlertDescription>
                </Alert>
              )}

              <div className="flex gap-3">
                <Button onClick={handleSyncQuickBooks} disabled={isSyncingQB} className="rounded-full">
                  {isSyncingQB ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Sync Now
                    </>
                  )}
                </Button>
                <Dialog open={showDisconnectQBDialog} onOpenChange={setShowDisconnectQBDialog}>
                  <DialogTrigger asChild>
                    <Button variant="outline" className="rounded-full">
                      <Unlink className="mr-2 h-4 w-4" />
                      Disconnect
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Disconnect QuickBooks</DialogTitle>
                      <DialogDescription>
                        Are you sure you want to disconnect your QuickBooks account? Your existing data
                        will remain, but automatic syncing will stop.
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowDisconnectQBDialog(false)}>
                        Cancel
                      </Button>
                      <Button variant="destructive" onClick={handleDisconnectQuickBooks}>
                        Disconnect
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Connect QuickBooks to automatically import your customers, invoices, bills, and bank
                balances.
              </p>
              <Button
                onClick={handleConnectQuickBooks}
                disabled={isConnectingQB}
                className="rounded-full bg-[#2CA01C] hover:bg-[#249017] text-white"
              >
                {isConnectingQB ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <Link2 className="mr-2 h-4 w-4" />
                    Connect to QuickBooks
                  </>
                )}
              </Button>
            </div>
          )}
        </NeuroCardContent>
      </NeuroCard>

      {/* Cash Buffer Rule */}
      <NeuroCard>
        <NeuroCardHeader>
          <NeuroCardTitle className="flex items-center gap-2 font-league-spartan text-xl font-bold text-gunmetal">
            <div className="w-10 h-10 rounded-xl bg-white/60 backdrop-blur-sm border border-white/30 flex items-center justify-center">
              <Shield className="h-5 w-5 text-gunmetal" />
            </div>
            Cash Buffer Rule
          </NeuroCardTitle>
          <NeuroCardDescription>
            Set your minimum runway threshold for safety alerts
          </NeuroCardDescription>
        </NeuroCardHeader>
        <NeuroCardContent className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label className="text-gunmetal font-medium">Minimum Months of Runway</Label>
              <Select value={bufferMonths} onValueChange={setBufferMonths}>
                <SelectTrigger className="bg-white/60 backdrop-blur-sm border-white/30">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">1 month</SelectItem>
                  <SelectItem value="2">2 months</SelectItem>
                  <SelectItem value="3">3 months (recommended)</SelectItem>
                  <SelectItem value="4">4 months</SelectItem>
                  <SelectItem value="6">6 months</SelectItem>
                  <SelectItem value="12">12 months</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={handleUpdateBufferRule} className="rounded-full">Save Rule</Button>
          </div>
          <p className="text-sm text-muted-foreground">
            You'll see a warning when your forecast shows cash falling below{' '}
            <span className="font-medium text-gunmetal">{bufferMonths} months</span> of operating expenses.
          </p>
        </NeuroCardContent>
      </NeuroCard>

      {/* Account Settings */}
      <NeuroCard>
        <NeuroCardHeader>
          <NeuroCardTitle className="flex items-center gap-2 font-league-spartan text-xl font-bold text-gunmetal">
            <div className="w-10 h-10 rounded-xl bg-white/60 backdrop-blur-sm border border-white/30 flex items-center justify-center">
              <SettingsIcon className="h-5 w-5 text-gunmetal" />
            </div>
            Account
          </NeuroCardTitle>
          <NeuroCardDescription>Manage your account settings</NeuroCardDescription>
        </NeuroCardHeader>
        <NeuroCardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-gunmetal font-medium">Email</Label>
            <Input value={user?.email || ''} disabled className="bg-white/60 backdrop-blur-sm border-white/30" />
          </div>
          <div className="space-y-2">
            <Label className="text-gunmetal font-medium">Base Currency</Label>
            <Input value={user?.base_currency || 'USD'} disabled className="bg-white/60 backdrop-blur-sm border-white/30" />
          </div>
          <div className="pt-4 border-t border-white/20">
            <Button variant="destructive" onClick={logout} className="rounded-full">
              Sign Out
            </Button>
          </div>
        </NeuroCardContent>
      </NeuroCard>
    </div>
  );
}
