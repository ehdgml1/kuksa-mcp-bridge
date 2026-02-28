/**
 * WebSocket connection status badge component.
 *
 * Displays a compact pill-shaped indicator showing the current
 * connection state to the Kuksa Databroker. Now rendered with
 * glassmorphism styling to match the IVI design system.
 *
 * Note: The primary connection state is shown in the DashboardLayout
 * StatusBar. This badge acts as a secondary fallback indicator when
 * the status bar is not visible (e.g. scroll or narrow layout).
 */

import type { ConnectionState } from "../../types/vss";

/** Props for the ConnectionBadge component. */
interface ConnectionBadgeProps {
  /** Current WebSocket connection state. */
  readonly state: ConnectionState;
  /** Error message shown as a tooltip on hover. */
  readonly error?: string | null;
}

/** Visual configuration for each connection state. */
const STATE_CONFIG: Record<ConnectionState, { color: string; label: string; pulse: boolean }> = {
  connected:    { color: "bg-gauge-green",  label: "Connected",    pulse: false },
  reconnecting: { color: "bg-gauge-amber",  label: "Reconnecting", pulse: true  },
  disconnected: { color: "bg-gauge-red",    label: "Disconnected", pulse: false },
};

/**
 * Fixed-position connection status badge.
 *
 * Renders a small glassmorphism pill in the lower-right corner
 * showing a colored dot and a status label. Pulses when reconnecting.
 * The badge is intentionally subtle — the StatusBar carries the
 * primary connection UI. This is a compact overflow indicator.
 */
export function ConnectionBadge({
  state,
  error,
}: ConnectionBadgeProps): React.ReactElement {
  const config = STATE_CONFIG[state];

  return (
    <div
      className="fixed bottom-3 right-3 z-50 flex items-center gap-2
                 glass-card px-3 py-1.5 shadow-lg animate-slide-in"
      title={error ?? undefined}
    >
      <span
        className={`w-2 h-2 rounded-full ${config.color} ${
          config.pulse ? "animate-pulse-slow" : ""
        }`}
      />
      <span className="text-[11px] font-medium text-ivi-secondary tracking-wide">
        {config.label}
      </span>
    </div>
  );
}
