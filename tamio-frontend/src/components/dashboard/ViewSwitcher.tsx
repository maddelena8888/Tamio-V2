/**
 * View Switcher - Dropdown to switch between preset views
 */

import { useState } from 'react';
import { User, Briefcase, Sparkles } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import { useDashboard } from '@/contexts/DashboardContext';
import { getPresetDisplayName } from './widgets/registry';
import type { ViewPreset } from './widgets/types';

export function ViewSwitcher() {
  const { activePreset, resetToPreset, isDirty } = useDashboard();
  const [pendingPreset, setPendingPreset] = useState<Exclude<ViewPreset, 'custom'> | null>(
    null
  );

  const handlePresetChange = (value: string) => {
    const preset = value as ViewPreset;

    // If switching away from custom or dirty state, confirm first
    if (preset !== 'custom' && (activePreset === 'custom' || isDirty)) {
      setPendingPreset(preset as Exclude<ViewPreset, 'custom'>);
    } else if (preset !== 'custom') {
      resetToPreset(preset as Exclude<ViewPreset, 'custom'>);
    }
  };

  const handleConfirmSwitch = () => {
    if (pendingPreset) {
      resetToPreset(pendingPreset);
      setPendingPreset(null);
    }
  };

  return (
    <>
      <Select value={activePreset} onValueChange={handlePresetChange}>
        <SelectTrigger className="w-[180px] bg-white/60 border-white/30">
          <SelectValue placeholder="Select view" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="leader">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4" />
              <span>Leader View</span>
            </div>
          </SelectItem>
          <SelectItem value="finance_manager">
            <div className="flex items-center gap-2">
              <Briefcase className="w-4 h-4" />
              <span>Finance Manager</span>
            </div>
          </SelectItem>
          {activePreset === 'custom' && (
            <SelectItem value="custom">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                <span>Custom</span>
              </div>
            </SelectItem>
          )}
        </SelectContent>
      </Select>

      {/* Confirmation Dialog */}
      <AlertDialog open={!!pendingPreset} onOpenChange={() => setPendingPreset(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Switch to {pendingPreset && getPresetDisplayName(pendingPreset)}?</AlertDialogTitle>
            <AlertDialogDescription>
              Your current layout has unsaved changes. Switching views will replace your
              current cards with the preset layout.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Current</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmSwitch}>
              Switch View
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
