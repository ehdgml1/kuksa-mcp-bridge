/**
 * Chat text input component with send button.
 *
 * Provides a multi-line textarea that auto-resizes up to
 * four lines, with Enter-to-send and Shift+Enter for newline.
 */

import { useCallback, useRef, useState } from "react";
import type { KeyboardEvent, ChangeEvent } from "react";

/** Props for the ChatInput component. */
interface ChatInputProps {
  /** Callback invoked when the user submits a message. */
  readonly onSend: (message: string) => void;
  /** Whether input is disabled (e.g., during streaming). */
  readonly disabled?: boolean;
}

/** Maximum textarea height in pixels (approximately 4 lines). */
const MAX_HEIGHT_PX = 120;

/** Base textarea height in pixels (single line). */
const BASE_HEIGHT_PX = 42;

/**
 * Auto-resizing chat input with send button.
 *
 * Renders a dark-themed textarea that grows with content
 * up to four lines. Supports keyboard shortcuts for
 * sending and creating newlines.
 */
export function ChatInput({
  onSend,
  disabled = false,
}: ChatInputProps): React.ReactElement {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /**
   * Reset textarea height to its base size.
   */
  const resetHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = `${String(BASE_HEIGHT_PX)}px`;
  }, []);

  /**
   * Auto-resize textarea based on scroll height.
   */
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = `${String(BASE_HEIGHT_PX)}px`;
    el.style.height = `${String(Math.min(el.scrollHeight, MAX_HEIGHT_PX))}px`;
  }, []);

  /**
   * Submit the current input value.
   */
  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (trimmed.length === 0 || disabled) return;
    onSend(trimmed);
    setValue("");
    resetHeight();
  }, [value, disabled, onSend, resetHeight]);

  /**
   * Handle keyboard events for send and newline shortcuts.
   */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  /**
   * Handle textarea value changes and auto-resize.
   */
  const handleChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      setValue(e.target.value);
      adjustHeight();
    },
    [adjustHeight],
  );

  const hasContent = value.trim().length > 0;

  return (
    <div className="flex items-end gap-2 p-3 border-t border-ivi-border">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="차량에 대해 물어보세요..."
        rows={1}
        className={`
          flex-1 resize-none bg-ivi-dark border border-ivi-border rounded-xl
          px-4 py-2.5 text-sm text-ivi-text placeholder-ivi-muted
          focus:outline-none focus:border-gauge-cyan/50
          transition-colors duration-200
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        `}
        style={{ height: `${String(BASE_HEIGHT_PX)}px` }}
      />

      <button
        type="button"
        onClick={handleSubmit}
        disabled={disabled || !hasContent}
        aria-label="Send message"
        className={`
          flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center
          transition-all duration-200
          ${
            hasContent && !disabled
              ? "bg-gauge-cyan text-ivi-dark hover:bg-gauge-cyan/80"
              : "bg-ivi-dark border border-ivi-border text-ivi-muted cursor-not-allowed"
          }
        `}
      >
        {/* Send arrow icon */}
        <svg viewBox="0 0 24 24" className="w-5 h-5 fill-current">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
        </svg>
      </button>
    </div>
  );
}
