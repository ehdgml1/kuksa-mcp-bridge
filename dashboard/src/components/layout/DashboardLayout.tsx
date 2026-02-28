/**
 * Main dashboard layout and status bar components.
 *
 * Provides a full-screen automotive IVI layout with a fixed top status bar,
 * a 60/40 split between vehicle gauge panels and the AI chat area,
 * and glassmorphism styling throughout.
 */

import { useState, useEffect } from "react";
import type { ReactNode } from "react";
import type { ConnectionState } from "../../types/vss";

// ─── StatusBar ────────────────────────────────────────────────────────────────

/** Props for the StatusBar component. */
interface StatusBarProps {
  /** Current WebSocket connection state to the Kuksa Databroker. */
  readonly connectionState: ConnectionState;
  /** Optional error message shown as a tooltip or sub-label. */
  readonly error?: string | null;
}

/** Visual configuration per connection state. */
const CONNECTION_CONFIG: Record<
  ConnectionState,
  { dot: string; label: string; pulse: boolean }
> = {
  connected:    { dot: "bg-gauge-green",  label: "Connected",      pulse: false },
  reconnecting: { dot: "bg-gauge-amber",  label: "Reconnecting",   pulse: true  },
  disconnected: { dot: "bg-gauge-red",    label: "Disconnected",   pulse: false },
};

/**
 * Minimal SVG car silhouette for the status bar brand area.
 * Renders as a single-path side-profile icon at 32x16 px.
 */
function CarSilhouette(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 48 24"
      width="48"
      height="24"
      aria-hidden="true"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Body */}
      <path
        d="M3 17 C3 17 5 13 9 11 L16 7 C19 5.5 24 5 28 5 L38 5.5 C41 5.8 43 7 44 9 L46 13 L46 17 Z"
        fill="rgba(6,182,212,0.5)"
        stroke="#06b6d4"
        strokeWidth="0.8"
      />
      {/* Roof cutout */}
      <path
        d="M12 11 L17 7.5 C20 6 25 5.5 29 5.5 L37 6 L40 9 L38 11 Z"
        fill="rgba(8,12,20,0.7)"
      />
      {/* Rear wheel */}
      <circle cx="11" cy="17" r="3.5" fill="#0f1724" stroke="#06b6d4" strokeWidth="1" />
      <circle cx="11" cy="17" r="1.5" fill="#06b6d4" />
      {/* Front wheel */}
      <circle cx="37" cy="17" r="3.5" fill="#0f1724" stroke="#06b6d4" strokeWidth="1" />
      <circle cx="37" cy="17" r="1.5" fill="#06b6d4" />
      {/* Ground line */}
      <line x1="4" y1="20.5" x2="44" y2="20.5" stroke="rgba(6,182,212,0.2)" strokeWidth="0.5" />
    </svg>
  );
}

/**
 * Top status bar for the IVI dashboard.
 *
 * Shows the vehicle brand icon and name on the left, a connection
 * state pill in the center, and a live clock on the right.
 * The clock updates every minute via a setInterval.
 */
export function StatusBar({ connectionState, error }: StatusBarProps): React.ReactElement {
  const [currentTime, setCurrentTime] = useState<string>(() => formatTime(new Date()));

  /** Format a Date object into a locale time string (e.g. "02:34 PM"). */
  function formatTime(date: Date): string {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  useEffect(() => {
    const id = setInterval(() => {
      setCurrentTime(formatTime(new Date()));
    }, 60_000);

    return () => clearInterval(id);
  }, []);

  const conn = CONNECTION_CONFIG[connectionState];

  return (
    <header className="glass-card rounded-none border-x-0 border-t-0 px-5 py-2 flex items-center justify-between">
      {/* ── Left: brand ── */}
      <div className="flex items-center gap-3">
        <CarSilhouette />
        <div className="flex flex-col leading-none">
          <span
            className="text-[10px] tracking-[0.25em] uppercase font-medium text-ivi-muted"
            style={{ fontVariantCaps: "all-small-caps" }}
          >
            Kuksa
          </span>
          <span className="text-sm font-semibold tracking-widest text-ivi-text glow-text-cyan">
            IVI
          </span>
        </div>
        <div className="w-px h-8 bg-white/10 ml-1" />
        <span className="text-xs text-ivi-muted tracking-wider font-medium">
          IONIQ 5
        </span>
      </div>

      {/* ── Center: connection pill ── */}
      <div
        className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-white/10 bg-white/[0.04]"
        title={error ?? undefined}
      >
        <span
          className={`w-2 h-2 rounded-full ${conn.dot} ${
            conn.pulse ? "animate-pulse-slow" : ""
          }`}
        />
        <span className="text-[11px] font-medium text-ivi-secondary tracking-wide">
          {conn.label}
        </span>
        {error && connectionState !== "connected" && (
          <span className="text-[10px] text-gauge-red ml-1 max-w-[180px] truncate">
            — {error}
          </span>
        )}
      </div>

      {/* ── Right: clock ── */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-ivi-muted tracking-wider">
          {new Date().toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
        </span>
        <div className="w-px h-4 bg-white/10" />
        <span className="text-base font-semibold font-instrument tabular-nums text-ivi-text glow-text-cyan">
          {currentTime}
        </span>
      </div>
    </header>
  );
}

// ─── DashboardLayout ──────────────────────────────────────────────────────────

/** Props for the DashboardLayout component. */
interface DashboardLayoutProps {
  /** Vehicle status gauge components rendered in the left panel grid. */
  readonly children: ReactNode;
  /** AI chat panel content rendered in the right panel. */
  readonly chatPanel?: ReactNode;
  /** Optional status bar override (renders above the main content). */
  readonly statusBar?: ReactNode;
}

/**
 * Two-column IVI dashboard layout.
 *
 * Renders a full-screen grid with:
 * - Left panel (60%): a 2-column auto-row grid for vehicle gauges and panels.
 * - Right panel (40%): the AI assistant chat area.
 *
 * The layout uses a transparent background so the body gradient shows through.
 * Stacks vertically on screens narrower than 1280 px.
 */
export function DashboardLayout({
  children,
  chatPanel,
  statusBar,
}: DashboardLayoutProps): React.ReactElement {
  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {statusBar}

      <main className="flex-1 min-h-0 overflow-hidden p-3 lg:p-4 flex flex-col">
        <div className="max-w-[1920px] mx-auto grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-3 lg:gap-4 flex-1 min-h-0 w-full">
          {/* Left panel: Vehicle gauges */}
          <div className="grid grid-cols-2 gap-3 grid-rows-[4fr_3fr_3fr] min-h-0">
            {children}
          </div>

          {/* Right panel: AI chat */}
          <div className="min-h-0 overflow-hidden">
            {chatPanel}
          </div>
        </div>
      </main>
    </div>
  );
}
