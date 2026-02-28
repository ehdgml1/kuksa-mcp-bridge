/**
 * AI assistant chat panel component.
 *
 * Full-height chat interface with message history, tool call
 * tracking, streaming indicators, and quick suggestion buttons.
 * Replaces the Phase 2 AiChatPlaceholder.
 */

import { useCallback, useEffect, useRef } from "react";
import { useAgentChat } from "../../hooks/useAgentChat";
import { ChatInput } from "./ChatInput";
import { ChatMessage } from "./ChatMessage";

/** Quick suggestion displayed when chat is empty. */
interface QuickSuggestion {
  readonly label: string;
  readonly message: string;
}

/** Pre-defined quick suggestion prompts. */
const QUICK_SUGGESTIONS: readonly QuickSuggestion[] = [
  { label: "차량 상태 점검", message: "차량 전반적인 상태를 점검해주세요." },
  { label: "엔진 진단", message: "엔진에 이상이 있는지 진단해주세요." },
  { label: "에어컨 24도로 설정", message: "에어컨 온도를 24도로 설정해주세요." },
  { label: "배터리 상태 확인", message: "배터리 상태를 확인해주세요." },
];

/**
 * Streaming indicator with pulsing dots.
 *
 * Shown at the bottom of the message list while the
 * assistant is generating a response.
 */
function StreamingIndicator(): React.ReactElement {
  return (
    <div className="flex items-center gap-1.5 px-4 py-2">
      <div className="w-2 h-2 rounded-full bg-gauge-cyan animate-pulse" />
      <div
        className="w-2 h-2 rounded-full bg-gauge-cyan animate-pulse"
        style={{ animationDelay: "150ms" }}
      />
      <div
        className="w-2 h-2 rounded-full bg-gauge-cyan animate-pulse"
        style={{ animationDelay: "300ms" }}
      />
    </div>
  );
}

/**
 * Main AI chat panel for the IVI dashboard.
 *
 * Renders a full-height flex column containing a header,
 * scrollable message list with auto-scroll, and a chat
 * input. When empty, shows welcome text and quick
 * suggestion pills.
 */
export function AiChatPanel(): React.ReactElement {
  const { messages, isStreaming, error, sendMessage, clearMessages } =
    useAgentChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or streaming updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const handleSuggestionClick = useCallback(
    (suggestion: QuickSuggestion) => {
      sendMessage(suggestion.message);
    },
    [sendMessage],
  );

  const hasMessages = messages.length > 0;
  const hasError = error !== null;

  return (
    <div className="h-full rounded-2xl bg-ivi-card border border-ivi-border flex flex-col min-h-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-ivi-border">
        <div className="flex items-center gap-2.5">
          {/* Brain/sparkle icon */}
          <svg viewBox="0 0 24 24" className="w-5 h-5 fill-gauge-cyan">
            <path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61z" />
          </svg>
          <h2 className="text-ivi-text text-sm font-bold">AI Assistant</h2>
          {/* Connection status dot */}
          <div
            className={`w-2 h-2 rounded-full ${hasError ? "bg-gauge-red" : "bg-gauge-green"}`}
            title={hasError ? `Error: ${error}` : "Connected"}
          />
        </div>

        {/* Clear button (visible only when messages exist) */}
        {hasMessages && (
          <button
            type="button"
            onClick={clearMessages}
            className="text-ivi-muted text-xs hover:text-ivi-text transition-colors"
            aria-label="Clear chat"
          >
            초기화
          </button>
        )}
      </div>

      {/* Error banner */}
      {hasError && (
        <div className="mx-3 mt-2 px-3 py-2 bg-gauge-red/10 border border-gauge-red/30 rounded-lg text-gauge-red text-xs">
          {error}
        </div>
      )}

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-3 py-3">
        {hasMessages ? (
          <>
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isStreaming && <StreamingIndicator />}
            <div ref={messagesEndRef} />
          </>
        ) : (
          /* Empty state with welcome and suggestions */
          <div className="h-full flex flex-col items-center justify-center px-4">
            {/* Welcome icon */}
            <svg
              viewBox="0 0 24 24"
              className="w-12 h-12 mb-4 fill-ivi-muted/20"
            >
              <path d="M21.928 11.607c-.202-.488-.635-.605-.928-.633V8c0-1.103-.897-2-2-2h-6V4.61c.305-.274.5-.668.5-1.11a1.5 1.5 0 0 0-3 0c0 .442.195.836.5 1.11V6H5c-1.103 0-2 .897-2 2v2.997l-.082.006A1 1 0 0 0 1.99 12v2a1 1 0 0 0 1 1H3v5c0 1.103.897 2 2 2h14c1.103 0 2-.897 2-2v-5a1 1 0 0 0 1-1v-1.938a1.006 1.006 0 0 0-.072-.455zM5 20V8h14l.001 3.996L19 12v2l.001.005.001 5.995H5z" />
              <ellipse cx={8.5} cy={12} rx={1.5} ry={2} />
              <ellipse cx={15.5} cy={12} rx={1.5} ry={2} />
              <path d="M8 16h8v2H8z" />
            </svg>

            <h3 className="text-ivi-text text-base font-semibold mb-1">
              AI Vehicle Assistant
            </h3>
            <p className="text-ivi-muted text-xs text-center mb-6 max-w-[220px]">
              자연어로 차량 상태를 조회하고 제어할 수 있습니다.
            </p>

            {/* Quick suggestion pills */}
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion.label}
                  type="button"
                  onClick={() => {
                    handleSuggestionClick(suggestion);
                  }}
                  className="
                    bg-ivi-dark border border-ivi-border rounded-full
                    px-4 py-2 text-xs text-ivi-muted
                    hover:border-gauge-cyan hover:text-ivi-text
                    transition-colors duration-200
                  "
                >
                  {suggestion.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Chat input */}
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
