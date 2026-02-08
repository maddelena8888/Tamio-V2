import { useState, useEffect, useMemo } from 'react';
import { ArrowLeft, X } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { useRules } from '@/contexts/RulesContext';
import { RuleTypeSelector } from './RuleTypeSelector';
import { RuleConfigForm } from './RuleConfigForm';
import { RuleAlertPreferences } from './RuleAlertPreferences';
import {
  type RuleType,
  type RuleConfig,
  type AlertPreferences,
  RULE_TYPES,
  DEFAULT_ALERT_PREFERENCES,
  generateRuleDescription,
} from '@/lib/api/rules';
import { toast } from 'sonner';

type CreateStep = 'type' | 'config' | 'alerts';

interface CreateRuleState {
  step: CreateStep;
  ruleType: RuleType | null;
  name: string;
  config: RuleConfig | null;
  alertPreferences: AlertPreferences;
}

const INITIAL_STATE: CreateRuleState = {
  step: 'type',
  ruleType: null,
  name: '',
  config: null,
  alertPreferences: DEFAULT_ALERT_PREFERENCES,
};

export function CreateRuleSheet() {
  const { isCreateSheetOpen, closeCreateSheet, editingRule, closeEditSheet, createRule, updateRule } = useRules();
  const isEditing = !!editingRule;
  const isOpen = isCreateSheetOpen || isEditing;

  const [state, setState] = useState<CreateRuleState>(INITIAL_STATE);

  // Initialize state when opening for edit
  useEffect(() => {
    if (editingRule) {
      setState({
        step: 'config',
        ruleType: editingRule.rule_type,
        name: editingRule.name,
        config: editingRule.config,
        alertPreferences: editingRule.alert_preferences,
      });
    } else if (isCreateSheetOpen) {
      setState(INITIAL_STATE);
    }
  }, [editingRule, isCreateSheetOpen]);

  const handleClose = () => {
    if (isEditing) {
      closeEditSheet();
    } else {
      closeCreateSheet();
    }
    // Reset state after animation
    setTimeout(() => setState(INITIAL_STATE), 300);
  };

  const steps: CreateStep[] = ['type', 'config', 'alerts'];
  const currentStepIndex = steps.indexOf(state.step);

  const canProceed = useMemo(() => {
    switch (state.step) {
      case 'type':
        return state.ruleType !== null;
      case 'config':
        return state.config !== null && state.name.trim() !== '';
      case 'alerts':
        return state.alertPreferences.show_in_feed || state.alertPreferences.send_email || state.alertPreferences.send_slack;
    }
  }, [state]);

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setState((prev) => ({ ...prev, step: steps[currentStepIndex + 1] }));
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setState((prev) => ({ ...prev, step: steps[currentStepIndex - 1] }));
    }
  };

  const handleTypeSelect = (type: RuleType) => {
    const typeInfo = RULE_TYPES.find((t) => t.type === type);
    setState((prev) => ({
      ...prev,
      ruleType: type,
      name: prev.name || typeInfo?.defaultName || '',
      config: typeInfo?.defaultConfig || null,
    }));
  };

  const handleConfigChange = (config: RuleConfig, name: string) => {
    setState((prev) => ({ ...prev, config, name }));
  };

  const handleAlertPreferencesChange = (prefs: AlertPreferences) => {
    setState((prev) => ({ ...prev, alertPreferences: prefs }));
  };

  const handleSubmit = () => {
    if (!state.ruleType || !state.config) return;

    if (isEditing && editingRule) {
      updateRule(editingRule.id, {
        name: state.name,
        description: generateRuleDescription({
          rule_type: state.ruleType,
          config: state.config,
        } as Parameters<typeof generateRuleDescription>[0]),
        config: state.config,
        alert_preferences: state.alertPreferences,
      });
      toast.success('Rule updated');
    } else {
      createRule({
        name: state.name,
        rule_type: state.ruleType,
        config: state.config,
        alert_preferences: state.alertPreferences,
      });
      toast.success('Rule created');
    }

    handleClose();
  };

  const stepTitle = useMemo(() => {
    switch (state.step) {
      case 'type':
        return 'Choose Rule Type';
      case 'config':
        return 'Configure Rule';
      case 'alerts':
        return 'Alert Preferences';
    }
  }, [state.step]);

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="space-y-4 pb-6 border-b border-white/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {currentStepIndex > 0 && !isEditing && (
                <Button variant="ghost" size="icon" onClick={handleBack} className="h-8 w-8">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              )}
              {isEditing && (
                <Button variant="ghost" size="icon" onClick={handleClose} className="h-8 w-8">
                  <X className="h-4 w-4" />
                </Button>
              )}
              <SheetTitle className="font-league-spartan">
                {isEditing ? 'Edit Rule' : 'Create Rule'}
              </SheetTitle>
            </div>
            {!isEditing && (
              <span className="text-sm text-muted-foreground">
                Step {currentStepIndex + 1} of {steps.length}
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">{stepTitle}</p>
        </SheetHeader>

        <div className="py-6">
          {state.step === 'type' && (
            <RuleTypeSelector
              selectedType={state.ruleType}
              onSelect={handleTypeSelect}
            />
          )}

          {state.step === 'config' && state.ruleType && state.config && (
            <RuleConfigForm
              ruleType={state.ruleType}
              config={state.config}
              name={state.name}
              onChange={handleConfigChange}
            />
          )}

          {state.step === 'alerts' && (
            <RuleAlertPreferences
              preferences={state.alertPreferences}
              onChange={handleAlertPreferencesChange}
            />
          )}
        </div>

        <div className="flex justify-end gap-3 pt-6 border-t border-white/30">
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          {state.step === 'alerts' || isEditing ? (
            <Button onClick={handleSubmit} disabled={!canProceed}>
              {isEditing ? 'Save Changes' : 'Create Rule'}
            </Button>
          ) : (
            <Button onClick={handleNext} disabled={!canProceed}>
              Next
            </Button>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
