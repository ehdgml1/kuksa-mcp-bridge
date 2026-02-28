/**
 * Tool call status card component.
 *
 * Displays a compact card within assistant messages showing
 * the status of MCP tool invocations (calling, done, error).
 */

import { useCallback, useState } from "react";
import type { ToolCallInfo } from "../../types/chat";

/** Props for the ToolCallCard component. */
interface ToolCallCardProps {
  /** Tool call information to display. */
  readonly toolCall: ToolCallInfo;
}

/** Maximum characters shown in the collapsed result preview. */
const PREVIEW_MAX_LENGTH = 120;

/**
 * Truncate text to a maximum length with ellipsis.
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum character count
 * @returns Truncated text with ellipsis if needed
 */
function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * Compact card showing tool execution status within a chat message.
 *
 * Renders the tool name with a status indicator (spinning for
 * calling, checkmark for done, X for error). When complete,
 * shows a truncated result preview that expands on click.
 */
export function ToolCallCard({
  toolCall,
}: ToolCallCardProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false);

  const toggleExpanded = useCallback(() => {
    if (toolCall.status === "done" && toolCall.result) {
      setExpanded((prev) => !prev);
    }
  }, [toolCall.status, toolCall.result]);

  return (
    <div
      className={`
        bg-ivi-dark/50 border border-ivi-border/50 rounded-lg px-3 py-2 text-sm
        ${toolCall.status === "done" && toolCall.result ? "cursor-pointer hover:border-ivi-border" : ""}
      `}
      onClick={toggleExpanded}
      role={toolCall.status === "done" && toolCall.result ? "button" : undefined}
      tabIndex={toolCall.status === "done" && toolCall.result ? 0 : undefined}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleExpanded();
        }
      }}
    >
      <div className="flex items-center gap-2">
        {/* Status icon */}
        {toolCall.status === "calling" && (
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4 text-gauge-amber animate-spin flex-shrink-0"
          >
            <circle
              cx={12}
              cy={12}
              r={10}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeDasharray="31.4 31.4"
              strokeLinecap="round"
            />
          </svg>
        )}
        {toolCall.status === "done" && (
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4 text-gauge-green flex-shrink-0 fill-current"
          >
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
          </svg>
        )}
        {toolCall.status === "error" && (
          <svg
            viewBox="0 0 24 24"
            className="w-4 h-4 text-gauge-red flex-shrink-0 fill-current"
          >
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        )}

        {/* Tool name */}
        <span className="font-mono text-ivi-text/80">{toolCall.name}</span>

        {/* Status text */}
        {toolCall.status === "calling" && (
          <span className="text-gauge-amber text-xs ml-auto">호출 중...</span>
        )}
        {toolCall.status === "done" && toolCall.result && (
          <svg
            viewBox="0 0 24 24"
            className={`w-3.5 h-3.5 text-ivi-muted ml-auto flex-shrink-0 fill-current
              transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          >
            <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" />
          </svg>
        )}
      </div>

      {/* Result preview / expanded result */}
      {toolCall.status === "done" && toolCall.result && (
        <div className="mt-1.5 text-ivi-muted text-xs">
          {expanded ? (
            <pre className="whitespace-pre-wrap break-all font-mono bg-ivi-dark p-2 rounded overflow-x-auto max-h-48 overflow-y-auto">
              {toolCall.result}
            </pre>
          ) : (
            <span>{truncate(toolCall.result, PREVIEW_MAX_LENGTH)}</span>
          )}
        </div>
      )}

      {/* Error message */}
      {toolCall.status === "error" && toolCall.result && (
        <div className="mt-1.5 text-gauge-red text-xs">{toolCall.result}</div>
      )}
    </div>
  );
}
