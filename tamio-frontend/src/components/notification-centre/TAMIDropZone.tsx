import { useState, useRef, useEffect } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { Bot, Send, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useNotificationCentre, type DraggedNotificationItem } from './NotificationCentreContext';
import { useTAMI } from '@/contexts/TAMIContext';

function generateContextualPrompt(item: DraggedNotificationItem): string {
  switch (item.type) {
    case 'alert':
      return `What should I do about this alert: "${item.title}"?`;
    case 'activity':
      return `Tell me more about this: "${item.title}"`;
    case 'rule':
      return `How am I tracking against my rule: "${item.title}"?`;
    default:
      return `Help me understand: "${item.title}"`;
  }
}

function DroppedItemBadge({
  item,
  onRemove,
}: {
  item: DraggedNotificationItem;
  onRemove: () => void;
}) {
  const typeColors = {
    alert: 'bg-tomato/10 text-tomato border-tomato/20',
    activity: 'bg-sky-500/10 text-sky-600 border-sky-500/20',
    rule: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  };

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-lg border mb-2',
        typeColors[item.type]
      )}
    >
      <span className="text-xs font-medium capitalize">{item.type}:</span>
      <span className="text-xs truncate max-w-[200px]">{item.title}</span>
      <button
        onClick={onRemove}
        className="ml-auto p-0.5 rounded hover:bg-black/10 transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}

export function TAMIDropZone() {
  const { droppedItem, setDroppedItem, close } = useNotificationCentre();
  const { sendMessage, isLoading, open: openTAMI } = useTAMI();
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { isOver, setNodeRef } = useDroppable({
    id: 'tami-drop-zone',
  });

  // Auto-populate input when item is dropped
  useEffect(() => {
    if (droppedItem) {
      const prompt = generateContextualPrompt(droppedItem);
      setInput(prompt);
      inputRef.current?.focus();
    }
  }, [droppedItem]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const message = input.trim();

    // Close notification centre and open TAMI drawer
    close();
    openTAMI();

    // Send the message with context
    await sendMessage(message);

    // Clear state
    setInput('');
    setDroppedItem(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearDropped = () => {
    setDroppedItem(null);
    setInput('');
  };

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'border-t p-4 transition-colors',
        isOver && 'bg-lime/5 border-t-lime'
      )}
    >
      {/* Drop indicator */}
      {isOver && !droppedItem && (
        <div className="flex items-center gap-2 text-lime-600 mb-3 animate-pulse">
          <Bot className="w-5 h-5" />
          <span className="text-sm font-medium">Release to ask TAMI</span>
        </div>
      )}

      {/* Dropped item badge */}
      {droppedItem && (
        <DroppedItemBadge item={droppedItem} onRemove={handleClearDropped} />
      )}

      {/* Input area */}
      <div className="flex items-end gap-2">
        {!isOver && !droppedItem && (
          <div className="flex items-center gap-2 text-gray-400 mr-2">
            <Bot className="w-5 h-5" />
          </div>
        )}

        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isOver
              ? 'Release to ask TAMI...'
              : droppedItem
                ? 'Ask TAMI about this...'
                : 'Drop a notification or type to ask TAMI...'
          }
          disabled={isLoading}
          rows={1}
          className={cn(
            'flex-1 resize-none rounded-xl border px-3 py-2',
            'text-sm placeholder:text-gray-400',
            'focus:outline-none focus:ring-2 focus:ring-lime/50 focus:border-lime',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'max-h-24',
            isOver ? 'border-lime bg-lime/5' : 'border-gray-200'
          )}
          style={{ minHeight: '40px' }}
        />

        <Button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="h-10 w-10 p-0 bg-lime hover:bg-lime/90 text-gunmetal rounded-xl flex-shrink-0"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </Button>
      </div>

      {/* Helper text */}
      {!droppedItem && !isOver && (
        <p className="text-[10px] text-gray-400 mt-2 text-center">
          Drag any notification card here to ask TAMI about it
        </p>
      )}
    </div>
  );
}
