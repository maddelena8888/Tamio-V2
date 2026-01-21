import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { saveBusinessProfile } from '@/lib/api/auth';
import { NeuroCard, NeuroCardContent } from '@/components/ui/neuro-card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowRight, Loader2 } from 'lucide-react';
import type { Industry, ProfessionalSubcategory, RevenueRange, Currency } from '@/lib/api/types';

// Industry options
const INDUSTRIES: { value: Industry; label: string }[] = [
  { value: 'professional_services', label: 'Professional Services' },
  { value: 'construction', label: 'Construction & Trades' },
  { value: 'real_estate', label: 'Real Estate & Property Management' },
  { value: 'healthcare', label: 'Healthcare Services' },
  { value: 'technology', label: 'Technology & Software' },
  { value: 'creative', label: 'Creative & Media' },
  { value: 'hospitality', label: 'Hospitality & Events' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'other', label: 'Other' },
];

// Subcategory options for Professional Services
const SUBCATEGORIES: { value: ProfessionalSubcategory; label: string }[] = [
  { value: 'marketing_agency', label: 'Marketing/Advertising Agency' },
  { value: 'consulting', label: 'Management Consulting' },
  { value: 'legal', label: 'Legal Services' },
  { value: 'accounting', label: 'Accounting/Finance' },
  { value: 'design_agency', label: 'Design/Creative Agency' },
  { value: 'it_services', label: 'IT Services' },
];

// Revenue range options
const REVENUE_RANGES: { value: RevenueRange; label: string }[] = [
  { value: '0-500k', label: 'Less than $500k' },
  { value: '500k-2m', label: '$500k - $2M' },
  { value: '2m-5m', label: '$2M - $5M' },
  { value: '5m-15m', label: '$5M - $15M' },
  { value: '15m+', label: '$15M+' },
];

// Currency options
const CURRENCIES: { value: Currency; label: string }[] = [
  { value: 'USD', label: 'USD - US Dollar' },
  { value: 'EUR', label: 'EUR - Euro' },
  { value: 'GBP', label: 'GBP - British Pound' },
  { value: 'AED', label: 'AED - UAE Dirham' },
  { value: 'AUD', label: 'AUD - Australian Dollar' },
  { value: 'CAD', label: 'CAD - Canadian Dollar' },
  { value: 'CHF', label: 'CHF - Swiss Franc' },
  { value: 'SGD', label: 'SGD - Singapore Dollar' },
  { value: 'JPY', label: 'JPY - Japanese Yen' },
  { value: 'NZD', label: 'NZD - New Zealand Dollar' },
];

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

export default function OnboardingBusinessProfile() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  const [industry, setIndustry] = useState<Industry | ''>('');
  const [subcategory, setSubcategory] = useState<ProfessionalSubcategory | ''>('');
  const [revenueRange, setRevenueRange] = useState<RevenueRange | ''>('');
  const [baseCurrency, setBaseCurrency] = useState<Currency | ''>('');

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate required fields
    if (!industry) {
      setError('Please select your industry');
      return;
    }
    if (!revenueRange) {
      setError('Please select your annual revenue range');
      return;
    }
    if (!baseCurrency) {
      setError('Please select your operating currency');
      return;
    }

    setIsSubmitting(true);

    try {
      await saveBusinessProfile({
        industry,
        subcategory: industry === 'professional_services' && subcategory ? subcategory : undefined,
        revenue_range: revenueRange,
        base_currency: baseCurrency,
      });

      // Refresh user to get updated profile
      await refreshUser();

      // Navigate to data source selection
      navigate('/onboarding');
    } catch (err) {
      console.error('Failed to save business profile:', err);
      setError(getErrorMessage(err, 'Failed to save business profile. Please try again.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectClassName = "w-full rounded-lg border border-gray-200 bg-white/60 backdrop-blur-sm px-4 py-3 focus:border-tomato focus:ring-2 focus:ring-tomato/20 focus:outline-none transition-colors appearance-none cursor-pointer";

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-10">
          <img
            src="/logo-dark.svg"
            alt="Tamio"
            className="h-12 mx-auto"
          />
          <h2 className="font-league-spartan font-bold text-3xl mt-10 text-gunmetal">
            Tell us about you
          </h2>
          <p className="text-muted-foreground mt-4 max-w-lg mx-auto text-base leading-relaxed">
            This helps us provide better insights tailored to you
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Form Card */}
        <NeuroCard>
          <NeuroCardContent className="p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Industry Field */}
              <div>
                <label className="block font-league-spartan font-semibold mb-2 text-gunmetal">
                  Industry <span className="text-tomato">*</span>
                </label>
                <select
                  value={industry}
                  onChange={(e) => {
                    setIndustry(e.target.value as Industry);
                    // Clear subcategory if changing away from professional services
                    if (e.target.value !== 'professional_services') {
                      setSubcategory('');
                    }
                  }}
                  className={selectClassName}
                  disabled={isSubmitting}
                >
                  <option value="">Select your industry...</option>
                  {INDUSTRIES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Conditional subcategory for Professional Services */}
              {industry === 'professional_services' && (
                <div>
                  <label className="block font-league-spartan font-semibold mb-2 text-gunmetal">
                    Business Type
                  </label>
                  <select
                    value={subcategory}
                    onChange={(e) => setSubcategory(e.target.value as ProfessionalSubcategory)}
                    className={selectClassName}
                    disabled={isSubmitting}
                  >
                    <option value="">Select type (optional)...</option>
                    {SUBCATEGORIES.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Revenue Size Field */}
              <div>
                <label className="block font-league-spartan font-semibold mb-2 text-gunmetal">
                  Annual Revenue <span className="text-tomato">*</span>
                </label>
                <select
                  value={revenueRange}
                  onChange={(e) => setRevenueRange(e.target.value as RevenueRange)}
                  className={selectClassName}
                  disabled={isSubmitting}
                >
                  <option value="">Select revenue range...</option>
                  {REVENUE_RANGES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Operating Currency Field */}
              <div>
                <label className="block font-league-spartan font-semibold mb-2 text-gunmetal">
                  Operating Currency <span className="text-tomato">*</span>
                </label>
                <p className="text-sm text-muted-foreground mb-2">
                  All amounts will be displayed in this currency
                </p>
                <select
                  value={baseCurrency}
                  onChange={(e) => setBaseCurrency(e.target.value as Currency)}
                  className={selectClassName}
                  disabled={isSubmitting}
                >
                  <option value="">Select currency...</option>
                  {CURRENCIES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                disabled={isSubmitting}
                className="w-full rounded-full bg-gradient-to-r from-tomato to-tomato/80 hover:from-tomato/90 hover:to-tomato/70 text-white font-semibold py-6 text-base shadow-lg shadow-tomato/20 transition-all duration-300 mt-8"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    Continue to Setup
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </>
                )}
              </Button>
            </form>
          </NeuroCardContent>
        </NeuroCard>

        {/* Footer Note */}
        <p className="text-center text-sm text-muted-foreground mt-8">
          You can update this information later in Settings.
        </p>
      </div>
    </div>
  );
}
