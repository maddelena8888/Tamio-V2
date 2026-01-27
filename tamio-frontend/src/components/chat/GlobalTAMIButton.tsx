/**
 * GlobalTAMIButton - Floating Action Button for TAMI Chatbot
 *
 * Fixed position button in the bottom-right corner that opens the global TAMI drawer.
 * Appears on all protected pages via MainLayout.
 */

import { Bot } from 'lucide-react';
import { useTAMI } from '@/contexts/TAMIContext';
import { cn } from '@/lib/utils';

export function GlobalTAMIButton() {
  const { toggle, isOpen } = useTAMI();

  return (
    <button
      onClick={toggle}
      className={cn(
        'fixed bottom-6 right-6',
        'w-14 h-14',
        'rounded-full',
        'bg-lime hover:bg-lime/90',
        'text-gunmetal',
        'shadow-lg hover:shadow-xl',
        'transition-all duration-200',
        'hover:scale-105',
        'flex items-center justify-center',
        'z-50',
        // Hide when drawer is open to avoid z-index conflicts
        isOpen && 'opacity-0 pointer-events-none'
      )}
      aria-label="Chat with TAMI"
      aria-expanded={isOpen}
    >
      <Bot className="w-6 h-6" />
    </button>
  );
}
