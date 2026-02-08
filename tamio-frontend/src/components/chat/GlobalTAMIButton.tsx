/**
 * GlobalTAMIButton - Floating Action Button for TAMI Chatbot
 *
 * Fixed position button in the bottom-right corner that opens the global TAMI drawer.
 * Appears on all protected pages via MainLayout (except Home which has its own AI input).
 */

import { Bot } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useTAMI } from '@/contexts/TAMIContext';
import { cn } from '@/lib/utils';

export function GlobalTAMIButton() {
  const { toggle, isOpen } = useTAMI();
  const location = useLocation();

  // Hide on home page - it has its own AI input in the bottom bar
  if (location.pathname === '/home') {
    return null;
  }

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
