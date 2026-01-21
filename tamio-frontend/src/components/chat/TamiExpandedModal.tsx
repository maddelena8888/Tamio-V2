/**
 * TamiExpandedModal - Fullscreen Tami chat modal
 *
 * Features:
 * - Preserves conversation history from embedded widget
 * - Maintains scroll position on expand/collapse
 * - Full-width chat interface for extended conversations
 */

import { useRef, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  User,
  AlertTriangle,
  ArrowRight,
  Minimize2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import { StructuredResponse } from '@/components/chat/StructuredResponse';
import type { ChatMode, SuggestedAction } from '@/lib/api/types';

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  mode?: ChatMode;
  suggestedActions?: SuggestedAction[];
  showScenarioBanner?: boolean;
  isStreaming?: boolean;
  showInlineCards?: boolean;
}

interface TamiExpandedModalProps {
  isOpen: boolean;
  onClose: () => void;
  messages: DisplayMessage[];
  input: string;
  setInput: (value: string) => void;
  onSend: (text?: string) => Promise<void>;
  isLoading: boolean;
  getModeLabel: (mode?: ChatMode) => string;
  onActionClick: (action: SuggestedAction) => Promise<void>;
}

const TypingIndicator = () => (
  <div className="flex items-center gap-1.5 py-1">
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce [animation-delay:-0.3s]" />
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce [animation-delay:-0.15s]" />
    <span className="w-2 h-2 bg-lime rounded-full animate-bounce" />
  </div>
);

export function TamiExpandedModal({
  isOpen,
  onClose,
  messages,
  input,
  setInput,
  onSend,
  isLoading,
  getModeLabel,
  onActionClick,
}: TamiExpandedModalProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollAreaRef.current) {
      const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages]);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl h-[90vh] p-0 flex flex-col bg-white/95 backdrop-blur-xl border-white/20">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="font-semibold text-gunmetal text-lg">Ask Tami</h2>
            <p className="text-sm text-gray-500">Run scenarios, check forecasts, or explore your cash position</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8 text-gray-400 hover:text-gunmetal"
          >
            <Minimize2 className="w-4 h-4" />
          </Button>
        </div>

        {/* Messages Area */}
        <ScrollArea className="flex-1 h-full" ref={scrollAreaRef}>
          <div className="p-6">
            <div className="space-y-4 max-w-3xl mx-auto">
              {messages.map((message, index) => (
                <div key={index}>
                  <div className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {message.role === 'assistant' && (
                      <Avatar className="h-8 w-8 flex-shrink-0">
                        <AvatarFallback className="bg-gradient-to-br from-lime to-lime/70 text-gunmetal font-bold text-sm">
                          T
                        </AvatarFallback>
                      </Avatar>
                    )}
                    <div className={`max-w-[80%] ${message.role === 'user' ? 'bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-3 shadow-sm' : 'space-y-2'}`}>
                      {message.role === 'assistant' && message.mode && !message.isStreaming && (
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="secondary" className="text-xs px-2 py-0.5 bg-muted/80">
                            {getModeLabel(message.mode)}
                          </Badge>
                        </div>
                      )}

                      {message.role === 'assistant' && message.showScenarioBanner && (
                        <div className="p-2 bg-lime/10 border border-lime/30 rounded-lg text-xs mb-2 flex items-center gap-2">
                          <AlertTriangle className="h-3.5 w-3.5 text-lime" />
                          <span className="font-medium">Scenario editing mode active</span>
                        </div>
                      )}

                      {message.role === 'assistant' ? (
                        message.isStreaming && message.content === '' ? (
                          <TypingIndicator />
                        ) : message.isStreaming ? (
                          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-1.5 text-sm">
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          </div>
                        ) : (
                          <StructuredResponse content={message.content} />
                        )
                      ) : (
                        <p className="leading-relaxed text-sm">{message.content}</p>
                      )}

                      {message.role === 'assistant' && !message.isStreaming && message.suggestedActions && message.suggestedActions.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-border/50">
                          {message.suggestedActions.map((action, actionIndex) => (
                            <Button
                              key={actionIndex}
                              variant={action.action === 'none' ? 'outline' : 'default'}
                              size="sm"
                              className={cn('text-xs h-8', action.action !== 'none' && 'bg-primary hover:bg-primary/90')}
                              onClick={() => onActionClick(action)}
                            >
                              {action.label}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                    {message.role === 'user' && (
                      <Avatar className="h-8 w-8 border-2 border-muted flex-shrink-0">
                        <AvatarFallback className="bg-muted">
                          <User className="h-4 w-4" />
                        </AvatarFallback>
                      </Avatar>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-100 bg-gray-50/50">
          <div className="relative max-w-3xl mx-auto">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your cash, obligations, or scenarios..."
              disabled={isLoading}
              className="pr-14 h-12 rounded-xl bg-white border-gray-200 focus:border-lime focus:ring-lime/30 text-base"
            />
            <Button
              onClick={() => onSend()}
              disabled={!input.trim() || isLoading}
              size="icon"
              className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 rounded-lg bg-lime hover:bg-lime/90 text-gunmetal transition-all"
            >
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
