import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import { useAuth } from './AuthContext';
import {
  type Rule,
  type RulesFilter,
  type CreateRuleInput,
  type UpdateRuleInput,
  type RuleConfig,
  loadRulesFromStorage,
  saveRulesToStorage,
  generateRuleId,
  generateRuleDescription,
} from '@/lib/api/rules';

// ============================================================================
// Context Types
// ============================================================================

interface RulesContextValue {
  // Data
  rules: Rule[];
  isLoading: boolean;

  // Filtering
  activeFilter: RulesFilter;
  setActiveFilter: (filter: RulesFilter) => void;
  filteredRules: Rule[];

  // Filter counts for tabs
  filterCounts: {
    all: number;
    active: number;
    triggered_today: number;
  };

  // CRUD operations
  createRule: (input: CreateRuleInput) => Rule;
  updateRule: (id: string, input: UpdateRuleInput) => void;
  deleteRule: (id: string) => void;
  duplicateRule: (id: string) => Rule | undefined;
  toggleRuleStatus: (id: string) => void;

  // Create sheet state
  isCreateSheetOpen: boolean;
  openCreateSheet: () => void;
  closeCreateSheet: () => void;

  // Edit sheet state
  editingRule: Rule | null;
  openEditSheet: (rule: Rule) => void;
  closeEditSheet: () => void;

  // Utility
  getRuleById: (id: string) => Rule | undefined;
}

const RulesContext = createContext<RulesContextValue | undefined>(undefined);

// ============================================================================
// Provider
// ============================================================================

interface RulesProviderProps {
  children: ReactNode;
}

export function RulesProvider({ children }: RulesProviderProps) {
  const { user } = useAuth();

  // Data state
  const [rules, setRules] = useState<Rule[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Filter state
  const [activeFilter, setActiveFilter] = useState<RulesFilter>('all');

  // Sheet state
  const [isCreateSheetOpen, setIsCreateSheetOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);

  // Load from localStorage on mount
  useEffect(() => {
    if (!user?.id) {
      setRules([]);
      setIsLoading(false);
      return;
    }

    const storedRules = loadRulesFromStorage(user.id);
    setRules(storedRules);
    setIsLoading(false);
  }, [user?.id]);

  // Persist to localStorage on change (debounced)
  useEffect(() => {
    if (!user?.id || isLoading) return;

    const timeoutId = setTimeout(() => {
      saveRulesToStorage(user.id, rules);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [user?.id, rules, isLoading]);

  // Filter counts
  const filterCounts = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    return {
      all: rules.length,
      active: rules.filter((r) => r.status === 'active').length,
      triggered_today: rules.filter((r) => r.last_triggered_at?.startsWith(today)).length,
    };
  }, [rules]);

  // Filtered rules
  const filteredRules = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];

    switch (activeFilter) {
      case 'active':
        return rules.filter((r) => r.status === 'active');
      case 'triggered_today':
        return rules.filter((r) => r.last_triggered_at?.startsWith(today));
      default:
        return rules;
    }
  }, [rules, activeFilter]);

  // CRUD operations
  const createRule = useCallback(
    (input: CreateRuleInput): Rule => {
      if (!user?.id) throw new Error('User not authenticated');

      const newRule: Rule = {
        id: generateRuleId(),
        user_id: user.id,
        name: input.name,
        description: input.description || generateRuleDescription({
          rule_type: input.rule_type,
          config: input.config,
        } as Rule),
        rule_type: input.rule_type,
        config: input.config,
        alert_preferences: input.alert_preferences,
        status: 'active',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_triggered_at: null,
        trigger_count: 0,
      };

      setRules((prev) => [...prev, newRule]);
      return newRule;
    },
    [user?.id]
  );

  const updateRule = useCallback((id: string, input: UpdateRuleInput) => {
    setRules((prev) =>
      prev.map((rule) => {
        if (rule.id !== id) return rule;

        const updatedRule = {
          ...rule,
          ...input,
          config: input.config ? ({ ...rule.config, ...input.config } as RuleConfig) : rule.config,
          alert_preferences: input.alert_preferences
            ? { ...rule.alert_preferences, ...input.alert_preferences }
            : rule.alert_preferences,
          updated_at: new Date().toISOString(),
        };

        // Regenerate description if config changed and no custom description
        if (input.config && !input.description) {
          updatedRule.description = generateRuleDescription(updatedRule);
        }

        return updatedRule;
      })
    );
  }, []);

  const deleteRule = useCallback((id: string) => {
    setRules((prev) => prev.filter((rule) => rule.id !== id));
  }, []);

  const duplicateRule = useCallback(
    (id: string): Rule | undefined => {
      if (!user?.id) return undefined;

      const original = rules.find((r) => r.id === id);
      if (!original) return undefined;

      const duplicated: Rule = {
        ...original,
        id: generateRuleId(),
        name: `${original.name} (Copy)`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_triggered_at: null,
        trigger_count: 0,
      };

      setRules((prev) => [...prev, duplicated]);
      return duplicated;
    },
    [user?.id, rules]
  );

  const toggleRuleStatus = useCallback((id: string) => {
    setRules((prev) =>
      prev.map((rule) => {
        if (rule.id !== id) return rule;
        return {
          ...rule,
          status: rule.status === 'active' ? 'paused' : 'active',
          updated_at: new Date().toISOString(),
        };
      })
    );
  }, []);

  // Sheet controls
  const openCreateSheet = useCallback(() => setIsCreateSheetOpen(true), []);
  const closeCreateSheet = useCallback(() => setIsCreateSheetOpen(false), []);
  const openEditSheet = useCallback((rule: Rule) => setEditingRule(rule), []);
  const closeEditSheet = useCallback(() => setEditingRule(null), []);

  // Utility
  const getRuleById = useCallback((id: string) => rules.find((r) => r.id === id), [rules]);

  const value: RulesContextValue = {
    rules,
    isLoading,
    activeFilter,
    setActiveFilter,
    filteredRules,
    filterCounts,
    createRule,
    updateRule,
    deleteRule,
    duplicateRule,
    toggleRuleStatus,
    isCreateSheetOpen,
    openCreateSheet,
    closeCreateSheet,
    editingRule,
    openEditSheet,
    closeEditSheet,
    getRuleById,
  };

  return <RulesContext.Provider value={value}>{children}</RulesContext.Provider>;
}

// ============================================================================
// Hook
// ============================================================================

export function useRules(): RulesContextValue {
  const context = useContext(RulesContext);
  if (!context) {
    throw new Error('useRules must be used within a RulesProvider');
  }
  return context;
}
