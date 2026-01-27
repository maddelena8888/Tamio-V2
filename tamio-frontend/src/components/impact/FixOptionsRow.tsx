import { FixOptionCard } from './FixOptionCard';
import type { FixRecommendation } from './types';

interface FixOptionsRowProps {
  fixes: FixRecommendation[];
  onSelectFix: (fix: FixRecommendation) => void;
}

export function FixOptionsRow({ fixes, onSelectFix }: FixOptionsRowProps) {
  // Ensure we have exactly 3 fix slots (pad with empty placeholders if needed)
  const displayFixes = fixes.slice(0, 3);

  if (displayFixes.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">No fix recommendations available</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
      {displayFixes.map((fix, index) => (
        <FixOptionCard
          key={fix.id}
          number={(index + 1) as 1 | 2 | 3}
          fix={fix}
          onSelect={() => onSelectFix(fix)}
        />
      ))}
    </div>
  );
}
