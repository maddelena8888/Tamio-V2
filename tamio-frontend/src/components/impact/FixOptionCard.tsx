import { Button } from '@/components/ui/button';
import type { FixRecommendation } from './types';

interface FixOptionCardProps {
  number: 1 | 2 | 3;
  fix: FixRecommendation;
  onSelect: () => void;
}

export function FixOptionCard({ number, fix, onSelect }: FixOptionCardProps) {
  return (
    <div className="flex-1 p-6 rounded-2xl bg-white/40 backdrop-blur-md border border-white/20 shadow-lg hover:shadow-xl transition-shadow">
      {/* Number badge - matching design */}
      <div className="text-center mb-4">
        <span className="text-sm text-gunmetal/60">Fix #{number}</span>
      </div>

      {/* Title */}
      <h3 className="font-semibold text-gunmetal text-center mb-2">
        {fix.title}
      </h3>

      {/* Description */}
      <p className="text-sm text-muted-foreground text-center mb-4 line-clamp-2">
        {fix.description}
      </p>

      {/* Impact indicator */}
      {fix.buffer_improvement && (
        <div className="flex items-center justify-center gap-2 mb-4">
          <span className="text-sm font-medium text-lime-700 bg-lime/20 px-2 py-1 rounded">
            {fix.buffer_improvement}
          </span>
        </div>
      )}

      {/* Apply button */}
      <Button
        onClick={onSelect}
        className="w-full bg-gunmetal hover:bg-gunmetal/90 text-white"
      >
        Apply Fix
      </Button>
    </div>
  );
}
