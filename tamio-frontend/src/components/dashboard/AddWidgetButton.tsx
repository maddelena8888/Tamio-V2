/**
 * Add Widget Button - Opens the widget library sheet
 */

import { useState } from 'react';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { WidgetLibrarySheet } from './WidgetLibrarySheet';

interface AddWidgetButtonProps {
  className?: string;
}

export function AddWidgetButton({ className }: AddWidgetButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
        variant="outline"
        className={className}
      >
        <Plus className="w-4 h-4 mr-2" />
        Add Card
      </Button>

      <WidgetLibrarySheet open={isOpen} onOpenChange={setIsOpen} />
    </>
  );
}
