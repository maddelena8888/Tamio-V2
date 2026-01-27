/**
 * TAMIContext - Global AI Chatbot Context
 *
 * Provides global state for the TAMI chatbot:
 * - Drawer open/close state
 * - Conversation history and messages
 * - Page context registration for context-aware responses
 * - Session persistence
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { sendChatMessageStreaming, type StreamEvent } from '@/lib/api/tami';

// ============================================================================
// Types
// ============================================================================

export interface TAMIPageData {
  // Alert pages
  currentAlert?: { id: string; title: string; severity: string };
  decisionQueueCount?: number;

  // Forecast page
  timeRange?: string;
  activeScenario?: { id: string; name: string };
  excludedTransactionsCount?: number;
  runwayWeeks?: number;

  // Scenario builder
  builderMode?: 'suggested' | 'manual';
  scenarioType?: string;

  // Generic
  selectedEntity?: { type: string; id: string; name: string };

  // Allow additional custom data
  [key: string]: unknown;
}

export interface TAMIPageContext {
  page: string;
  route: string;
  routeParams?: Record<string, string>;
  pageData?: TAMIPageData;
}

export interface TAMIChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

interface TAMIContextValue {
  // Drawer state
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;

  // Chat state
  messages: TAMIChatMessage[];
  isLoading: boolean;
  sessionId: string | null;

  // Page context
  pageContext: TAMIPageContext | null;
  registerPageContext: (context: Partial<TAMIPageContext>) => void;
  clearPageContext: () => void;

  // Actions
  sendMessage: (message: string) => Promise<void>;
  clearConversation: () => void;
  setSessionId: (sessionId: string | null) => void;
}

const TAMIContext = createContext<TAMIContextValue | undefined>(undefined);

// ============================================================================
// Suggested Prompts by Page
// ============================================================================

export const SUGGESTED_PROMPTS: Record<string, string[]> = {
  'alerts-home': [
    'What should I do about this alert?',
    'Explain this risk to me',
    'Show me my options',
  ],
  'forecast': [
    'Explain my runway',
    'What if I lose my biggest client?',
    'How can I improve my cash position?',
  ],
  'alert-impact': [
    "What's the best fix for this?",
    'Compare these options',
    "What's the long-term impact?",
  ],
  'scenarios': [
    'Help me build a scenario',
    'What scenarios should I consider?',
    'Compare my scenarios',
  ],
  'alerts-actions': [
    'Prioritize my alerts',
    'What needs my attention first?',
    'Summarize my risks',
  ],
  'default': [
    'How can I improve my cash flow?',
    'What risks should I focus on?',
    'Help me understand my finances',
  ],
};

export function getSuggestedPrompts(page: string): string[] {
  return SUGGESTED_PROMPTS[page] || SUGGESTED_PROMPTS['default'];
}

// ============================================================================
// Provider
// ============================================================================

interface TAMIProviderProps {
  children: ReactNode;
}

export function TAMIProvider({ children }: TAMIProviderProps) {
  const { user } = useAuth();
  const location = useLocation();
  const params = useParams();

  // Drawer state
  const [isOpen, setIsOpen] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<TAMIChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(() => {
    // Restore from localStorage if available
    if (typeof window !== 'undefined' && user?.id) {
      return localStorage.getItem(`tami_global_session_${user.id}`);
    }
    return null;
  });

  // Page context state
  const [pageContext, setPageContext] = useState<TAMIPageContext | null>(null);

  // Persist session ID
  useEffect(() => {
    if (user?.id && sessionId) {
      localStorage.setItem(`tami_global_session_${user.id}`, sessionId);
    }
  }, [user?.id, sessionId]);

  // Update route info when location changes
  useEffect(() => {
    if (pageContext) {
      setPageContext((prev) =>
        prev
          ? {
              ...prev,
              route: location.pathname,
              routeParams: params as Record<string, string>,
            }
          : null
      );
    }
  }, [location.pathname, params]);

  // Drawer actions
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  // Page context registration
  const registerPageContext = useCallback(
    (context: Partial<TAMIPageContext>) => {
      setPageContext({
        page: context.page || 'unknown',
        route: location.pathname,
        routeParams: params as Record<string, string>,
        pageData: context.pageData,
      });
    },
    [location.pathname, params]
  );

  const clearPageContext = useCallback(() => {
    setPageContext(null);
  }, []);

  // Send message with streaming
  const sendMessage = useCallback(
    async (messageContent: string) => {
      if (!messageContent.trim() || !user) return;

      const userMessage: TAMIChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: messageContent,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      // Create assistant message placeholder for streaming
      const assistantMessageId = `msg-${Date.now() + 1}`;
      const assistantMessage: TAMIChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      try {
        await sendChatMessageStreaming(
          {
            user_id: user.id,
            message: messageContent,
            conversation_history: messages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            active_scenario_id: pageContext?.pageData?.activeScenario?.id || null,
            page_context: pageContext
              ? {
                  current_route: pageContext.route,
                  route_params: pageContext.routeParams,
                  page_data: pageContext.pageData,
                }
              : undefined,
          },
          // On chunk
          (chunk) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: m.content + chunk }
                  : m
              )
            );
          },
          // On done
          (event: StreamEvent) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId ? { ...m, isStreaming: false } : m
              )
            );
            setIsLoading(false);

            // Update session ID if returned
            if (event.context_summary?.session_id) {
              setSessionId(event.context_summary.session_id as string);
            }
          },
          // On error
          (error) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      content: `Sorry, I encountered an error: ${error}`,
                      isStreaming: false,
                    }
                  : m
              )
            );
            setIsLoading(false);
          }
        );
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId
              ? {
                  ...m,
                  content: 'Sorry, I encountered an unexpected error. Please try again.',
                  isStreaming: false,
                }
              : m
          )
        );
        setIsLoading(false);
      }
    },
    [user, messages, pageContext]
  );

  // Clear conversation
  const clearConversation = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    if (user?.id) {
      localStorage.removeItem(`tami_global_session_${user.id}`);
    }
  }, [user?.id]);

  const value: TAMIContextValue = {
    // Drawer state
    isOpen,
    open,
    close,
    toggle,

    // Chat state
    messages,
    isLoading,
    sessionId,

    // Page context
    pageContext,
    registerPageContext,
    clearPageContext,

    // Actions
    sendMessage,
    clearConversation,
    setSessionId,
  };

  return <TAMIContext.Provider value={value}>{children}</TAMIContext.Provider>;
}

// ============================================================================
// Hooks
// ============================================================================

export function useTAMI() {
  const context = useContext(TAMIContext);
  if (context === undefined) {
    throw new Error('useTAMI must be used within a TAMIProvider');
  }
  return context;
}

/**
 * Hook for pages to register their context with TAMI.
 * Call this in page components to provide context-aware chat.
 *
 * @example
 * useTAMIPageContext({
 *   page: 'forecast',
 *   pageData: {
 *     timeRange: '13w',
 *     activeScenario: { id: 'abc', name: 'Client Loss' },
 *   }
 * });
 */
export function useTAMIPageContext(context: {
  page: string;
  pageData?: TAMIPageData;
}) {
  const { registerPageContext, clearPageContext } = useTAMI();

  useEffect(() => {
    registerPageContext(context);

    return () => clearPageContext();
  }, [context.page, JSON.stringify(context.pageData)]);
}
