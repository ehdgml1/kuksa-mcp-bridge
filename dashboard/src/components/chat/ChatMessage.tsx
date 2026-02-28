/**
 * Chat message bubble component.
 *
 * Renders a single user or assistant message with role-based
 * styling, inline tool call cards, and basic text formatting.
 */

import type { ChatMessage as ChatMessageType } from "../../types/chat";
import { ToolCallCard } from "./ToolCallCard";

/** Props for the ChatMessage component. */
interface ChatMessageProps {
  /** Message data to render. */
  readonly message: ChatMessageType;
}

/**
 * Format a Date object as a short time string (HH:MM).
 *
 * @param date - Timestamp to format
 * @returns Formatted time string
 */
function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/**
 * Render formatted message content with basic markdown support.
 *
 * Supports **bold**, `inline code`, and ```code blocks```.
 * Converts newlines to <br /> outside of code blocks.
 *
 * @param content - Raw message text
 * @returns Array of React elements
 */
function renderContent(content: string): React.ReactNode[] {
  if (content.length === 0) return [];

  const nodes: React.ReactNode[] = [];
  const codeBlockRegex = /```(?:\w*\n)?([\s\S]*?)```/g;
  let lastIndex = 0;
  let blockMatch = codeBlockRegex.exec(content);

  while (blockMatch !== null) {
    // Render text before this code block
    if (blockMatch.index > lastIndex) {
      const textBefore = content.slice(lastIndex, blockMatch.index);
      nodes.push(...renderInlineText(textBefore, `pre-${String(blockMatch.index)}`));
    }

    // Render the code block
    const codeContent = blockMatch[1] ?? "";
    nodes.push(
      <pre
        key={`block-${String(blockMatch.index)}`}
        className="bg-ivi-dark p-3 rounded-lg overflow-x-auto my-2 text-xs font-mono text-ivi-text/90"
      >
        <code>{codeContent.trim()}</code>
      </pre>,
    );

    lastIndex = blockMatch.index + blockMatch[0].length;
    blockMatch = codeBlockRegex.exec(content);
  }

  // Render remaining text after last code block
  if (lastIndex < content.length) {
    const remaining = content.slice(lastIndex);
    nodes.push(...renderInlineText(remaining, "end"));
  }

  return nodes;
}

/**
 * Render inline text with bold and code formatting.
 *
 * @param text - Text segment to format
 * @param keyPrefix - Unique key prefix for React elements
 * @returns Array of React elements
 */
function renderInlineText(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Match **bold** and `code` patterns
  const inlineRegex = /(\*\*(.+?)\*\*)|(`([^`]+)`)/g;
  let lastIdx = 0;
  let inlineMatch = inlineRegex.exec(text);

  while (inlineMatch !== null) {
    // Plain text before this match
    if (inlineMatch.index > lastIdx) {
      const plain = text.slice(lastIdx, inlineMatch.index);
      nodes.push(...splitNewlines(plain, `${keyPrefix}-t-${String(lastIdx)}`));
    }

    if (inlineMatch[2] !== undefined) {
      // **bold** match
      nodes.push(
        <strong key={`${keyPrefix}-b-${String(inlineMatch.index)}`} className="font-semibold">
          {inlineMatch[2]}
        </strong>,
      );
    } else if (inlineMatch[4] !== undefined) {
      // `code` match
      nodes.push(
        <code
          key={`${keyPrefix}-c-${String(inlineMatch.index)}`}
          className="bg-ivi-dark/50 px-1 rounded text-gauge-cyan/80 text-xs font-mono"
        >
          {inlineMatch[4]}
        </code>,
      );
    }

    lastIdx = inlineMatch.index + inlineMatch[0].length;
    inlineMatch = inlineRegex.exec(text);
  }

  // Remaining plain text
  if (lastIdx < text.length) {
    nodes.push(...splitNewlines(text.slice(lastIdx), `${keyPrefix}-r`));
  }

  return nodes;
}

/**
 * Split text on newlines and interleave <br /> elements.
 *
 * @param text - Plain text that may contain newlines
 * @param keyPrefix - Unique key prefix for React elements
 * @returns Array of text nodes and <br /> elements
 */
function splitNewlines(text: string, keyPrefix: string): React.ReactNode[] {
  const parts = text.split("\n");
  const nodes: React.ReactNode[] = [];

  parts.forEach((part, idx) => {
    if (idx > 0) {
      nodes.push(<br key={`${keyPrefix}-br-${String(idx)}`} />);
    }
    if (part.length > 0) {
      nodes.push(part);
    }
  });

  return nodes;
}

/**
 * Chat message bubble with role-based styling.
 *
 * User messages appear right-aligned in cyan. Assistant
 * messages appear left-aligned in the card background.
 * Tool calls render as compact status cards before the
 * text content.
 */
export function ChatMessage({
  message,
}: ChatMessageProps): React.ReactElement {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`
          max-w-[85%] px-4 py-3 text-sm leading-relaxed
          ${
            isUser
              ? "bg-gauge-cyan/20 border border-gauge-cyan/30 rounded-2xl rounded-br-md text-ivi-text"
              : "bg-ivi-card border border-ivi-border rounded-2xl rounded-bl-md text-ivi-text"
          }
        `}
      >
        {/* Tool call cards (assistant only) */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="space-y-2 mb-2">
            {message.toolCalls.map((tc, idx) => (
              <ToolCallCard key={`${tc.name}-${String(idx)}`} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Message content */}
        {message.content.length > 0 && (
          <div>{renderContent(message.content)}</div>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs mt-1.5 ${isUser ? "text-gauge-cyan/40" : "text-ivi-muted/60"}`}
        >
          {formatTime(message.timestamp)}
        </div>
      </div>
    </div>
  );
}
