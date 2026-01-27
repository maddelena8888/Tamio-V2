import { cn } from '@/lib/utils';
import type { BuilderMode } from './mockData';

interface ModeToggleProps {
  mode: BuilderMode;
  onModeChange: (mode: BuilderMode) => void;
}

export function ModeToggle({ mode, onModeChange }: ModeToggleProps) {
  return (
    <div className="inline-flex items-center rounded-full bg-white/70 p-1 backdrop-blur-sm border border-gunmetal/10 shadow-sm">
      <button
        type="button"
        onClick={() => onModeChange('suggested')}
        className={cn(
          'px-5 py-2 text-sm font-medium rounded-full transition-all duration-200',
          mode === 'suggested'
            ? 'bg-tomato/15 text-gunmetal shadow-sm'
            : 'bg-transparent text-gunmetal/70 hover:text-gunmetal'
        )}
      >
        Suggested
      </button>
      <button
        type="button"
        onClick={() => onModeChange('manual')}
        className={cn(
          'px-5 py-2 text-sm font-medium rounded-full transition-all duration-200',
          mode === 'manual'
            ? 'bg-tomato/15 text-gunmetal shadow-sm'
            : 'bg-transparent text-gunmetal/70 hover:text-gunmetal'
        )}
      >
        Manual
      </button>
    </div>
  );
}
