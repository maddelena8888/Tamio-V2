/**
 * Dashboard Card Menu - ⋮ dropdown menu with Configure and Remove actions
 */

import { useState } from 'react';
import { MoreVertical, Settings, Trash2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';

interface DashboardCardMenuProps {
  onConfigure?: () => void;
  onRemove: () => void;
}

export function DashboardCardMenu({ onConfigure, onRemove }: DashboardCardMenuProps) {
  const [showRemoveDialog, setShowRemoveDialog] = useState(false);

  const handleRemoveClick = () => {
    setShowRemoveDialog(true);
  };

  const handleConfirmRemove = () => {
    onRemove();
    setShowRemoveDialog(false);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-7 w-7 text-muted-foreground hover:text-gunmetal"
          >
            <MoreVertical className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          {onConfigure && (
            <DropdownMenuItem onClick={onConfigure}>
              <Settings className="mr-2 h-4 w-4" />
              Configure
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            onClick={handleRemoveClick}
            className="text-tomato focus:text-tomato"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Remove Confirmation Dialog */}
      <AlertDialog open={showRemoveDialog} onOpenChange={setShowRemoveDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove card?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the card from your dashboard. You can add it back anytime
              from the widget library.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmRemove}
              className="bg-tomato hover:bg-tomato/90"
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
