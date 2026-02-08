/**
 * Dashboard Context - State management for customizable Health dashboard
 *
 * Manages:
 * - View presets (Leader, Finance Manager, Custom)
 * - Widget instances and their order
 * - Widget-specific settings
 * - localStorage persistence with user-scoping
 */

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
import type {
  ViewPreset,
  WidgetConfig,
  WidgetId,
  DashboardState,
} from '@/components/dashboard/widgets/types';
import { PRESET_CONFIGS, WIDGET_REGISTRY } from '@/components/dashboard/widgets/registry';

// ============================================================================
// Constants
// ============================================================================

const STORAGE_VERSION = 1;
const STORAGE_KEY_PREFIX = 'tamio_dashboard_';

// ============================================================================
// Context Types
// ============================================================================

interface DashboardContextValue {
  // State
  state: DashboardState;
  isLoading: boolean;

  // View management
  activePreset: ViewPreset;
  setViewPreset: (preset: ViewPreset) => void;
  resetToPreset: (preset: Exclude<ViewPreset, 'custom'>) => void;

  // Widget management
  widgets: WidgetConfig[];
  addWidget: (widgetId: WidgetId) => void;
  removeWidget: (instanceId: string) => void;
  reorderWidgets: (sourceIndex: number, destinationIndex: number) => void;
  updateWidgetSettings: (instanceId: string, settings: Record<string, unknown>) => void;

  // Utility
  isDirty: boolean;
  getStorageKey: () => string;
}

const DashboardContext = createContext<DashboardContextValue | undefined>(undefined);

// ============================================================================
// Utility Functions
// ============================================================================

function generateInstanceId(widgetId: WidgetId): string {
  return `${widgetId}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function createWidgetFromPreset(widgetId: WidgetId): WidgetConfig {
  const definition = WIDGET_REGISTRY[widgetId];
  return {
    id: generateInstanceId(widgetId),
    widgetId,
    settings: definition?.defaultSettings ?? {},
  };
}

function getDefaultState(preset: ViewPreset = 'leader'): DashboardState {
  const widgetIds = preset === 'custom' ? [] : PRESET_CONFIGS[preset];
  return {
    version: STORAGE_VERSION,
    viewPreset: preset,
    widgets: widgetIds.map(createWidgetFromPreset),
    lastModified: new Date().toISOString(),
  };
}

function loadStateFromStorage(userId: string): DashboardState | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${userId}`);
    if (!stored) return null;

    const parsed = JSON.parse(stored) as DashboardState;

    // Version migration if needed
    if (!parsed.version || parsed.version < STORAGE_VERSION) {
      // For now, just use defaults if version mismatch
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

function saveStateToStorage(userId: string, state: DashboardState): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(
      `${STORAGE_KEY_PREFIX}${userId}`,
      JSON.stringify({ ...state, version: STORAGE_VERSION })
    );
  } catch (error) {
    console.error('Failed to save dashboard state:', error);
  }
}

// ============================================================================
// Provider Component
// ============================================================================

export function DashboardProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [state, setState] = useState<DashboardState>(() => getDefaultState('leader'));

  // Load state from localStorage when user changes
  useEffect(() => {
    if (!user?.id) {
      setState(getDefaultState('leader'));
      setIsLoading(false);
      return;
    }

    const storedState = loadStateFromStorage(user.id);
    if (storedState) {
      setState(storedState);
    } else {
      // Default to Leader View for first-time users
      setState(getDefaultState('leader'));
    }
    setIsLoading(false);
  }, [user?.id]);

  // Persist to localStorage on state change (debounced)
  useEffect(() => {
    if (!user?.id || isLoading) return;

    const timeoutId = setTimeout(() => {
      saveStateToStorage(user.id, state);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [user?.id, state, isLoading]);

  // View preset management
  const setViewPreset = useCallback((preset: ViewPreset) => {
    setState((prev) => ({
      ...prev,
      viewPreset: preset,
      lastModified: new Date().toISOString(),
    }));
  }, []);

  const resetToPreset = useCallback((preset: Exclude<ViewPreset, 'custom'>) => {
    const widgetIds = PRESET_CONFIGS[preset];
    setState({
      version: STORAGE_VERSION,
      viewPreset: preset,
      widgets: widgetIds.map(createWidgetFromPreset),
      lastModified: new Date().toISOString(),
    });
  }, []);

  // Widget management
  const addWidget = useCallback((widgetId: WidgetId) => {
    setState((prev) => ({
      ...prev,
      viewPreset: 'custom',
      widgets: [...prev.widgets, createWidgetFromPreset(widgetId)],
      lastModified: new Date().toISOString(),
    }));
  }, []);

  const removeWidget = useCallback((instanceId: string) => {
    setState((prev) => ({
      ...prev,
      viewPreset: 'custom',
      widgets: prev.widgets.filter((w) => w.id !== instanceId),
      lastModified: new Date().toISOString(),
    }));
  }, []);

  const reorderWidgets = useCallback((sourceIndex: number, destinationIndex: number) => {
    setState((prev) => {
      const newWidgets = [...prev.widgets];
      const [removed] = newWidgets.splice(sourceIndex, 1);
      newWidgets.splice(destinationIndex, 0, removed);

      return {
        ...prev,
        viewPreset: 'custom',
        widgets: newWidgets,
        lastModified: new Date().toISOString(),
      };
    });
  }, []);

  const updateWidgetSettings = useCallback(
    (instanceId: string, settings: Record<string, unknown>) => {
      setState((prev) => ({
        ...prev,
        viewPreset: 'custom',
        widgets: prev.widgets.map((w) =>
          w.id === instanceId ? { ...w, settings: { ...w.settings, ...settings } } : w
        ),
        lastModified: new Date().toISOString(),
      }));
    },
    []
  );

  // Check if current state differs from the active preset
  const isDirty = useMemo(() => {
    if (state.viewPreset === 'custom') return true;

    const presetWidgets = PRESET_CONFIGS[state.viewPreset as Exclude<ViewPreset, 'custom'>];
    if (state.widgets.length !== presetWidgets.length) return true;

    return state.widgets.some((w, i) => w.widgetId !== presetWidgets[i]);
  }, [state.viewPreset, state.widgets]);

  const getStorageKey = useCallback(() => {
    return user?.id ? `${STORAGE_KEY_PREFIX}${user.id}` : '';
  }, [user?.id]);

  const value: DashboardContextValue = {
    state,
    isLoading,
    activePreset: state.viewPreset,
    setViewPreset,
    resetToPreset,
    widgets: state.widgets,
    addWidget,
    removeWidget,
    reorderWidgets,
    updateWidgetSettings,
    isDirty,
    getStorageKey,
  };

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

// ============================================================================
// Hook
// ============================================================================

export function useDashboard(): DashboardContextValue {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}
