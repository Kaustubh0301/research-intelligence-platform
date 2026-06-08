"use client";

import { useRef, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { SendHorizonal } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}

export function ChatInput({ value, onChange, onSend, disabled }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSend();
    }
  };

  return (
    <div className="border-t bg-background p-3">
      <div className="flex items-end gap-2 max-w-3xl mx-auto">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
          rows={1}
          placeholder="Ask about the corpus… (Enter to send, Shift+Enter for newline)"
          className={cn(
            "flex-1 resize-none rounded-xl border bg-muted/50 px-4 py-3 text-sm",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
            "placeholder:text-muted-foreground min-h-[44px] max-h-[160px]",
            "overflow-y-auto leading-relaxed",
            disabled && "opacity-50 cursor-not-allowed"
          )}
          style={{ height: "auto" }}
          onInput={(e) => {
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = Math.min(el.scrollHeight, 160) + "px";
          }}
        />
        <Button
          className="h-11 w-11 rounded-xl shrink-0 p-0"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="Send"
        >
          <SendHorizonal className="h-4 w-4" />
        </Button>
      </div>
      <p className="text-center text-xs text-muted-foreground mt-1.5">
        Answers are grounded in the NeurIPS 2024 corpus only
      </p>
    </div>
  );
}
