import { useState } from 'react';
import { Mic, Send, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';

interface BottomBarProps {
  onAISubmit: (message: string) => Promise<void>;
}

export function BottomBar({ onAISubmit }: BottomBarProps) {
  const [value, setValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!value.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await onAISubmit(value);
      setValue('');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVoiceClick = () => {
    toast.info('Voice input coming soon');
  };

  return (
    <div className="flex items-stretch px-4 py-3 glass-subtle rounded-xl">
      <div className="flex-1 flex items-center glass rounded-xl p-1 transition-all focus-within:ring-2 focus-within:ring-lime/30">
        {/* AI Icon */}
        <div className="w-9 h-9 bg-gunmetal rounded-lg flex items-center justify-center m-0.5">
          <Sparkles className="w-4 h-4 text-lime" />
        </div>

        {/* Input */}
        <input
          type="text"
          data-ai-input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder='Ask anything... "Can I afford a hire?" "What if Acme pays late?"'
          className="flex-1 bg-transparent border-none text-gunmetal text-sm px-3 py-2.5 outline-none placeholder:text-muted-foreground"
          disabled={isSubmitting}
        />

        {/* Voice Button */}
        <button
          onClick={handleVoiceClick}
          className="w-9 h-9 rounded-lg bg-white/50 border border-white/30 text-muted-foreground cursor-pointer flex items-center justify-center m-0.5 transition-all hover:bg-gunmetal hover:text-white hover:border-gunmetal"
          title="Voice input"
        >
          <Mic className="w-4 h-4" />
        </button>

        {/* Send Button */}
        <Button
          onClick={handleSubmit}
          disabled={!value.trim() || isSubmitting}
          size="sm"
          className="w-9 h-9 rounded-lg m-0.5 bg-gunmetal hover:bg-gunmetal/90 disabled:opacity-50"
          title="Send"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
