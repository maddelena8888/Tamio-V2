import { Check, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

/**
 * EmptyAlertState - Displayed when no critical alerts require attention.
 * Shows a celebration state with a link to browse monitoring items.
 */
export function EmptyAlertState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-8rem)]">
      <div className="w-20 h-20 rounded-full bg-lime/20 flex items-center justify-center mb-6">
        <Check className="w-10 h-10 text-lime-700" strokeWidth={2.5} />
      </div>
      <h2 className="text-3xl font-bold text-gunmetal mb-3">All Clear</h2>
      <p className="text-lg text-muted-foreground mb-8 text-center max-w-md">
        No urgent alerts require your attention right now.
      </p>
      <Link
        to="/action-monitor"
        className="text-sm text-gunmetal/70 hover:text-gunmetal flex items-center gap-1.5 transition-colors group"
      >
        Browse all alerts
        <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
      </Link>
    </div>
  );
}
