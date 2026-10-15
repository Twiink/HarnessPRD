import { useState, useRef, KeyboardEvent } from 'react';
import { ArrowUp, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  loading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, loading, disabled, placeholder }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || loading || disabled) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-end gap-2 rounded border border-slate-300 bg-white p-1.5 focus-within:border-primary-600 focus-within:ring-1 focus-within:ring-primary-600">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          aria-label="回答或补充"
          placeholder={placeholder || '回答问题，或补充你想到的需求'}
          disabled={disabled || loading}
          rows={1}
          className="min-h-[40px] flex-1 resize-none bg-transparent px-2.5 py-2 text-[15px] leading-relaxed text-ink placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!input.trim() || loading || disabled}
          aria-label="发送"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded bg-primary-600 text-white transition-colors hover:bg-primary-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {loading ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> : <ArrowUp className="h-5 w-5" aria-hidden />}
        </button>
      </div>
      <p className="mt-1.5 text-xs text-slate-500">Enter 发送，Shift + Enter 换行</p>
    </div>
  );
}
