import { Button } from '@/components/ui/button';
import type { Risk } from '@/lib/api/alertsActions';

interface AlertHeroCardProps {
  alert: Risk;
  onViewImpact: () => void;
}

/**
 * AlertHeroCard - Full-screen hero card displaying the highest priority alert.
 *
 * Design specs:
 * - Max width: 800px, centered
 * - Padding: 64px
 * - Border radius: 24px
 * - Background: Glassomorphic with light tomato tint
 * - Subtle shadow with tomato-tinted border
 * - Title: 28px bold, centered
 * - Body text: 18px regular, centered
 */
export function AlertHeroCard({ alert, onViewImpact }: AlertHeroCardProps) {
  // Format cash impact for display
  const formatAmount = (amount: number | null): string => {
    if (!amount) return '';
    const absAmount = Math.abs(amount);
    if (absAmount >= 1000) {
      return `$${Math.round(absAmount / 1000)}k`;
    }
    return `$${absAmount.toLocaleString()}`;
  };

  return (
    <div
      className="
        w-full max-w-[800px] mx-auto
        alert-hero-glass
        rounded-3xl
        p-16
        shadow-[0_8px_32px_rgba(255,79,63,0.12),0_4px_16px_rgba(0,0,0,0.06)]
        text-center
      "
    >
      {/* Alert Title - Primary Driver Statement */}
      <h1 className="text-xl font-semibold text-gunmetal mb-4">
        {alert.primary_driver}
        {alert.cash_impact && (
          <span> ({formatAmount(alert.cash_impact)})</span>
        )}
        {' '}is now {alert.due_horizon_label?.toLowerCase() || 'overdue'}.
      </h1>

      {/* Impact Statement Subheading */}
      {alert.impact_statement && (
        <p className="text-base text-gunmetal/70 mb-8">
          {alert.impact_statement.replace(/, reducing your cash buffer$/i, '')}
        </p>
      )}

      {/* View Impact Button */}
      <Button
        onClick={onViewImpact}
        className="
          h-12 w-[200px]
          bg-tomato hover:bg-tomato/90
          text-white font-semibold
          rounded-lg
          shadow-md hover:shadow-lg
          transition-all duration-200
        "
      >
        View Impact
      </Button>
    </div>
  );
}
