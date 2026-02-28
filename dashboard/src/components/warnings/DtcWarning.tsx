/**
 * Diagnostic Trouble Code (DTC) warning component.
 *
 * Renders an automotive-style check engine warning card when active
 * DTC codes are present. Styled as a vehicle warning light panel with
 * a red glow, pulsing CEL icon, and pill-shaped code badges.
 * Returns null when the DTC list is empty.
 */

/** Props for the DtcWarning component. */
interface DtcWarningProps {
  /** Array of active DTC codes (e.g., ["P0301", "P0420"]) */
  readonly dtcCodes: string[];
}

/**
 * Check Engine Light (MIL) SVG icon.
 *
 * Approximates the standard malfunction indicator lamp silhouette
 * used in automotive instrument clusters. Rendered in red with a
 * pulse-critical animation when active.
 */
function CheckEngineLightIcon(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 48 48"
      className="w-10 h-10 pulse-critical"
      fill="none"
      aria-hidden="true"
    >
      {/* Engine block body */}
      <rect
        x="10"
        y="14"
        width="22"
        height="16"
        rx="1"
        stroke="#ef4444"
        strokeWidth="2"
        fill="rgba(239,68,68,0.08)"
      />
      {/* Cylinder head studs */}
      <path
        d="M16 14v-5h5v5M27 14v-5h5v5"
        stroke="#ef4444"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Exhaust ports (right side) */}
      <path
        d="M32 20h7M32 26h5"
        stroke="#ef4444"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* Intake port (left side) */}
      <path
        d="M10 22H3"
        stroke="#ef4444"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* Engine mount base */}
      <rect
        x="13"
        y="30"
        width="16"
        height="5"
        rx="1"
        stroke="#ef4444"
        strokeWidth="2"
        fill="rgba(239,68,68,0.08)"
      />
      {/* Lightning bolt — fault indicator in engine center */}
      <path
        d="M26 17l-5 6h5l-5 6"
        stroke="#ef4444"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * DTC warning card with automotive check engine light indicator.
 *
 * Renders a glassmorphism card with a red ambient glow listing all
 * active diagnostic trouble codes as pill-shaped badges. The card
 * slides in on mount and the CEL icon pulses to draw attention.
 * Returns null when no DTCs are active.
 */
export function DtcWarning({
  dtcCodes,
}: DtcWarningProps): React.ReactElement | null {
  if (dtcCodes.length === 0) {
    return null;
  }

  return (
    <div
      className="glass-card p-3
                 border border-red-500/30
                 shadow-[0_0_30px_rgba(239,68,68,0.15)]
                 animate-slide-in overflow-hidden"
    >
      {/* ── Header: icon + title + count ───────────────────────── */}
      <div className="flex items-start gap-4 mb-4">
        <CheckEngineLightIcon />

        <div className="flex flex-col gap-0.5">
          <h3 className="text-gauge-red text-sm font-bold uppercase tracking-widest glow-text-red">
            Check Engine
          </h3>
          <p className="text-ivi-muted text-xs">
            {dtcCodes.length} active code{dtcCodes.length > 1 ? "s" : ""}
          </p>
        </div>

        {/* Ambient glow accent — top-right corner decorative dot */}
        <div
          className="ml-auto w-2 h-2 rounded-full bg-gauge-red pulse-critical self-start mt-1"
          aria-hidden="true"
        />
      </div>

      {/* ── DTC code pills ─────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {dtcCodes.map((code) => (
          <span
            key={code}
            className="inline-flex items-center px-3 py-1.5 rounded-full
                       bg-red-500/10 border border-red-500/20
                       font-mono font-bold text-sm text-red-400"
          >
            {code}
          </span>
        ))}
      </div>
    </div>
  );
}
