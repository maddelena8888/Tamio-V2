// ============================================================================
// API Module Exports
// ============================================================================

// Client
export { api as default, setAccessToken, getAccessToken, clearAuth, ApiClientError } from './client';

// Auth
export {
  login,
  signup,
  getCurrentUser,
  refreshToken,
  completeOnboarding,
  logout,
  getStoredUser,
  isAuthenticated,
} from './auth';

// Data
export * from './data';

// Forecast
export * from './forecast';

// Scenarios
export {
  getRules,
  createRule,
  updateRule,
  deleteRule,
  getScenarios,
  getScenario,
  createScenario,
  updateScenario,
  deleteScenario,
  buildScenario,
  addScenarioLayer,
  saveScenario,
  getScenarioForecast,
  getScenarioSuggestions,
  evaluateBaseRules,
  seedScenario,
  submitScenarioAnswers,
  getScenarioPipelineStatus,
  commitScenario,
  discardScenario,
} from './scenarios';

// Actions
export {
  getActionQueue,
  getAction,
  approveAction,
  markExecuted,
  skipAction,
  overrideAction,
  getExecutionArtifacts,
  getExecutionQueue,
  getRecentActivity,
  type ActionQueue,
  type ActionCard,
  type ActionOption as ActionQueueOption,
  type ActionStatus,
  type Urgency,
  type RiskLevel as ActionRiskLevel,
  type ExecutionArtifacts,
  type RecentActivity,
} from './actions';

// Action Monitor
export {
  getProblemsToReview,
  getOutstandingActions,
  getActions,
  createAction,
  updateActionStatus,
  approveActionOption,
  rejectActionOption,
  dismissProblem,
  markActionComplete,
  archiveCompletedActions,
  getActionArtifacts,
  type Problem,
  type PreparedAction,
  type ActionOption as MonitorActionOption,
  type Severity,
  type RiskLevel as MonitorRiskLevel,
  type ActionOptionStatus,
  type ActionType,
  type KanbanStatus,
  type ProblemsResponse,
  type ActionsResponse,
  type OutstandingActionsResponse,
  type CreateActionRequest,
  type ActionStep,
  type ActionStepOwner,
  type ActionStepStatus,
  type LinkedAlert,
} from './actionMonitor';

// Xero
export * from './xero';

// Onboarding
export * from './onboarding';

// TAMI AI Assistant
export {
  sendChatMessage,
  sendChatMessageStreaming,
  createOrUpdateScenarioLayer,
  iterateScenarioLayer,
  discardScenarioLayer,
  getScenarioSuggestions as getTamiScenarioSuggestions,
  planGoal,
  getTamiContext,
  formatConversationHistory,
} from './tami';

// Alerts & Actions (V4 Risk/Controls Architecture)
export {
  getRisks,
  getRisk,
  dismissRisk,
  acknowledgeRisk,
  getControls,
  getControl,
  updateControlState,
  approveControl,
  rejectControl,
  completeControl,
  getControlsForRisk,
  getRisksForControl,
  mapSeverity,
  mapControlState,
  getControlStateLabel,
  getSeverityStyles,
  getControlStateStyles,
  type Risk,
  type Control,
  type RiskSeverity,
  type RiskStatus,
  type ControlState,
  type RiskFilters,
  type ControlFilters,
  type RejectedSuggestion,
} from './alertsActions';

// Types
export * from './types';
