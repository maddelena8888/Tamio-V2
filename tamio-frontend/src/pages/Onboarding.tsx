import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { finishOnboarding } from '@/lib/api/onboarding';
import { NeuroCard, NeuroCardContent, NeuroCardDescription, NeuroCardHeader, NeuroCardTitle } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Link2, FileSpreadsheet, ArrowRight, Check } from 'lucide-react';
import { getXeroConnectUrl } from '@/lib/api/xero';

// Helper to extract error message from various error types
function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) {
    return err.message;
  }
  if (typeof err === 'object' && err !== null) {
    const errorObj = err as Record<string, unknown>;
    if (typeof errorObj.detail === 'string') return errorObj.detail;
    if (typeof errorObj.message === 'string') return errorObj.message;
  }
  if (typeof err === 'string') return err;
  return fallback;
}

export default function Onboarding() {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [isConnectingXero, setIsConnectingXero] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConnectXero = async () => {
    if (!user) return;
    setError(null);
    setIsConnectingXero(true);
    try {
      const { auth_url } = await getXeroConnectUrl(user.id);
      window.location.href = auth_url;
    } catch (err) {
      console.error('Failed to get Xero auth URL:', err);
      setError(getErrorMessage(err, 'Failed to connect to Xero. Please check that the backend is running.'));
      setIsConnectingXero(false);
    }
  };

  const handleManualSetup = () => {
    navigate('/onboarding/manual');
  };

  const handleSkip = async () => {
    if (!user) return;
    setError(null);
    setIsSkipping(true);
    try {
      await finishOnboarding(user.id);
      await refreshUser();
      navigate('/');
    } catch (err) {
      console.error('Failed to skip onboarding:', err);
      setError(getErrorMessage(err, 'Failed to skip onboarding.'));
      setIsSkipping(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-3xl">
        {/* Header */}
        <div className="text-center mb-14">
          <img
            src="/logo-dark.svg"
            alt="Tamio"
            className="h-12 mx-auto"
          />
          <h2 className="font-league-spartan font-bold text-3xl mt-10 text-gunmetal">
            How would you like to get started?
          </h2>
          <p className="text-muted-foreground mt-4 max-w-lg mx-auto text-base leading-relaxed">
            Connect your accounting software for automatic data sync, or set up your forecast manually.
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-8">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Integration Options */}
        <div className="space-y-6 mb-8">
          {/* Xero Option */}
          <NeuroCard className="relative cursor-pointer group hover:scale-[1.02] hover:shadow-xl transition-all duration-300">
            <NeuroCardHeader>
              <div className="w-14 h-14 rounded-2xl bg-white/60 backdrop-blur-sm border border-white/30 flex items-center justify-center mb-5 shadow-sm">
                <Link2 className="w-7 h-7 text-[#13B5EA]" />
              </div>
              <NeuroCardTitle className="font-league-spartan text-2xl font-bold text-gunmetal">
                Connect Xero
              </NeuroCardTitle>
              <NeuroCardDescription className="text-base mt-2">
                Sync your Xero accounting data automatically.
              </NeuroCardDescription>
            </NeuroCardHeader>
            <NeuroCardContent>
              <ul className="space-y-3 text-sm text-muted-foreground mb-8">
                <li className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-lime/20 flex items-center justify-center flex-shrink-0">
                    <Check className="w-3 h-3 text-lime" strokeWidth={3} />
                  </div>
                  Import clients, invoices, and bills
                </li>
                <li className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-lime/20 flex items-center justify-center flex-shrink-0">
                    <Check className="w-3 h-3 text-lime" strokeWidth={3} />
                  </div>
                  Sync bank balances in real-time
                </li>
                <li className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-lime/20 flex items-center justify-center flex-shrink-0">
                    <Check className="w-3 h-3 text-lime" strokeWidth={3} />
                  </div>
                  Analyze payment behavior patterns
                </li>
              </ul>
              <Button
                onClick={handleConnectXero}
                className="w-full rounded-full bg-gradient-to-r from-tomato to-tomato/80 hover:from-tomato/90 hover:to-tomato/70 text-white font-semibold py-6 text-base shadow-lg shadow-tomato/20 transition-all duration-300"
                disabled={isConnectingXero}
              >
                {isConnectingXero ? 'Connecting...' : 'Connect Xero'}
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </NeuroCardContent>
          </NeuroCard>

          {/* Manual Option */}
          <NeuroCard className="relative cursor-pointer group hover:scale-[1.01] hover:shadow-xl transition-all duration-300">
            <div className="flex flex-col md:flex-row md:items-center p-2 gap-6">
              <div className="flex items-center gap-5 flex-1">
                <div className="w-14 h-14 rounded-2xl bg-white/60 backdrop-blur-sm border border-white/30 flex items-center justify-center flex-shrink-0 shadow-sm">
                  <FileSpreadsheet className="w-7 h-7 text-gunmetal" />
                </div>
                <div>
                  <h3 className="font-league-spartan text-xl font-bold text-gunmetal">Enter Manually</h3>
                  <p className="text-muted-foreground text-sm mt-1">
                    Build your forecast from scratch with a simple guided setup. Quick 5-minute process.
                  </p>
                </div>
              </div>
              <Button
                onClick={handleManualSetup}
                variant="outline"
                className="md:w-auto w-full rounded-full px-8 py-6 border-2 border-gunmetal/20 hover:border-gunmetal/40 hover:bg-white/50 font-semibold transition-all duration-300"
              >
                Start Manual Setup
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </div>
          </NeuroCard>
        </div>

        {/* Footer Note */}
        <p className="text-center text-sm text-muted-foreground mt-10">
          You can always connect or disconnect integrations later in Settings.
        </p>

        {/* Skip Option */}
        <div className="text-center mt-6">
          <Button
            variant="ghost"
            onClick={handleSkip}
            disabled={isSkipping || isConnectingXero}
            className="text-muted-foreground hover:text-foreground"
          >
            {isSkipping ? 'Skipping...' : 'Skip for now'}
          </Button>
        </div>
      </div>
    </div>
  );
}