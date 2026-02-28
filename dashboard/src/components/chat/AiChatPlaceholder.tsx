/**
 * Placeholder component for the AI chat panel.
 *
 * Displays a "Coming in Phase 3" message where the
 * AI assistant interface will eventually be placed.
 */

/**
 * AI chat panel placeholder.
 *
 * Dark card with centered icon and message indicating
 * the AI assistant feature is planned for Phase 3.
 */
export function AiChatPlaceholder(): React.ReactElement {
  return (
    <div className="h-full rounded-2xl bg-ivi-card border border-ivi-border
                    flex flex-col items-center justify-center p-8 min-h-[400px]">
      {/* Brain/AI icon */}
      <svg
        viewBox="0 0 24 24"
        className="w-16 h-16 mb-6 fill-ivi-muted/30"
      >
        <path d="M21.928 11.607c-.202-.488-.635-.605-.928-.633V8c0-1.103-.897-2-2-2h-6V4.61c.305-.274.5-.668.5-1.11a1.5 1.5 0 0 0-3 0c0 .442.195.836.5 1.11V6H5c-1.103 0-2 .897-2 2v2.997l-.082.006A1 1 0 0 0 1.99 12v2a1 1 0 0 0 1 1H3v5c0 1.103.897 2 2 2h14c1.103 0 2-.897 2-2v-5a1 1 0 0 0 1-1v-1.938a1.006 1.006 0 0 0-.072-.455zM5 20V8h14l.001 3.996L19 12v2l.001.005.001 5.995H5z" />
        <ellipse cx="8.5" cy="12" rx="1.5" ry="2" />
        <ellipse cx="15.5" cy="12" rx="1.5" ry="2" />
        <path d="M8 16h8v2H8z" />
      </svg>

      <h2 className="text-xl font-bold text-ivi-text mb-2">AI Assistant</h2>
      <p className="text-ivi-muted text-sm text-center max-w-xs">
        Natural language vehicle diagnostics and control — coming in Phase 3.
      </p>
    </div>
  );
}
