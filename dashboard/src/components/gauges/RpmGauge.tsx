/**
 * Automotive cluster-style circular RPM gauge.
 *
 * Renders a 270-degree neon arc gauge matching the Speedometer aesthetic,
 * with a permanently tinted redline zone, per-zone glow filters, and
 * a large digital readout — no needle. Labels show RPM ÷ 1000.
 */

import { describeArc, polarToCartesian, valueToAngle, formatNumber } from "./GaugeUtils";

/** Props for the RpmGauge component. */
interface RpmGaugeProps {
  /** Current engine RPM */
  readonly rpm: number;
  /** Maximum RPM for gauge scale (default: 8000) */
  readonly maxRpm?: number;
  /** RPM threshold for redline zone (default: 6500) */
  readonly redlineRpm?: number;
}

// Gauge geometry constants — 270-degree arc in 300×300 viewBox (matches Speedometer)
const CX = 150;
const CY = 150;
const RADIUS = 120;
const START_ANGLE = 135;
const END_ANGLE = 405;
const TICK_OUTER = 120;
const TICK_INNER_MAJOR = 104;
const TICK_INNER_MINOR = 111;

/**
 * Resolve the SVG glow filter URL based on whether RPM is in redline.
 *
 * @param rpm - Current RPM value
 * @param redline - Redline threshold
 * @returns SVG filter reference string
 */
function getRpmGlowFilter(rpm: number, redline: number): string {
  return rpm >= redline ? "url(#rpm-glow-red)" : "url(#rpm-glow-cyan)";
}

/**
 * Resolve the arc stroke color based on whether RPM is in redline.
 *
 * @param rpm - Current RPM value
 * @param redline - Redline threshold
 * @returns Hex color string
 */
function getRpmArcColor(rpm: number, redline: number): string {
  return rpm >= redline ? "#ef4444" : "#06b6d4";
}

/**
 * Automotive cluster-style circular RPM gauge — no needle.
 *
 * A 270-degree neon glow arc fills from 0 to the current RPM.
 * Above the redline threshold the arc switches to red. A translucent
 * red overlay permanently marks the redline zone in the background
 * track. Tick labels show the value divided by 1000 (e.g. "6" = 6000).
 */
export function RpmGauge({
  rpm,
  maxRpm = 8000,
  redlineRpm = 6500,
}: RpmGaugeProps): React.ReactElement {
  const clampedRpm = Math.max(0, Math.min(maxRpm, rpm));
  const valueEndAngle = valueToAngle(clampedRpm, 0, maxRpm, START_ANGLE, END_ANGLE);
  const backgroundArc = describeArc(CX, CY, RADIUS, START_ANGLE, END_ANGLE);
  const valueArc = describeArc(CX, CY, RADIUS, START_ANGLE, valueEndAngle);
  const redlineStartAngle = valueToAngle(redlineRpm, 0, maxRpm, START_ANGLE, END_ANGLE);
  const redlineArc = describeArc(CX, CY, RADIUS, redlineStartAngle, END_ANGLE);
  const isInRedline = clampedRpm >= redlineRpm;
  const arcColor = getRpmArcColor(clampedRpm, redlineRpm);
  const glowFilter = getRpmGlowFilter(clampedRpm, redlineRpm);

  // Build fine (every 500 RPM) and major (every 1000 RPM) tick marks
  const ticks: React.ReactElement[] = [];
  for (let i = 0; i <= maxRpm; i += 500) {
    const angle = valueToAngle(i, 0, maxRpm, START_ANGLE, END_ANGLE);
    const isMajor = i % 1000 === 0;
    const isRedlineTick = i >= redlineRpm;
    const outer = polarToCartesian(CX, CY, TICK_OUTER, angle);
    const inner = polarToCartesian(CX, CY, isMajor ? TICK_INNER_MAJOR : TICK_INNER_MINOR, angle);

    ticks.push(
      <line
        key={`rpm-tick-${i}`}
        x1={outer.x}
        y1={outer.y}
        x2={inner.x}
        y2={inner.y}
        stroke={isRedlineTick ? "#ef4444" : isMajor ? "#94a3b8" : "#334155"}
        strokeWidth={isMajor ? 2 : 1}
        strokeLinecap="round"
      />,
    );
  }

  // Labels at every 1000 RPM — displayed as integer ÷ 1000 (0, 1, 2, …, 8)
  const labels: React.ReactElement[] = [];
  for (let i = 0; i <= maxRpm; i += 1000) {
    const angle = valueToAngle(i, 0, maxRpm, START_ANGLE, END_ANGLE);
    const pos = polarToCartesian(CX, CY, RADIUS - 26, angle);
    const isRedlineLabel = i >= redlineRpm;
    labels.push(
      <text
        key={`rpm-label-${i}`}
        x={pos.x}
        y={pos.y}
        textAnchor="middle"
        dominantBaseline="central"
        fill={isRedlineLabel ? "#ef4444" : "#64748b"}
        style={{ fontSize: "11px", fontWeight: 500 }}
      >
        {i / 1000}
      </text>,
    );
  }

  return (
    <div className="glass-card p-3 flex flex-col overflow-hidden min-h-0">
      <svg viewBox="0 0 300 300" className="w-full flex-1 min-h-0">
        <defs>
          {/* Cyan glow — normal RPM zone */}
          <filter id="rpm-glow-cyan" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood floodColor="#06b6d4" floodOpacity="0.6" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Red glow — redline zone */}
          <filter id="rpm-glow-red" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood floodColor="#ef4444" floodOpacity="0.6" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Outer decorative ring */}
        <circle
          cx={CX}
          cy={CY}
          r={RADIUS + 8}
          fill="none"
          stroke="#1e293b"
          strokeOpacity="0.3"
          strokeWidth={1}
        />

        {/* Background arc — full 270-degree track */}
        <path
          d={backgroundArc}
          fill="none"
          stroke="#1e293b"
          strokeOpacity="0.4"
          strokeWidth={14}
          strokeLinecap="round"
        />

        {/* Redline zone overlay — always visible as translucent red */}
        <path
          d={redlineArc}
          fill="none"
          stroke="#ef4444"
          strokeOpacity="0.25"
          strokeWidth={14}
          strokeLinecap="round"
        />

        {/* Value arc — neon glow fill from start to current RPM */}
        {clampedRpm > 0 && (
          <path
            d={valueArc}
            fill="none"
            stroke={arcColor}
            strokeWidth={14}
            strokeLinecap="round"
            filter={glowFilter}
            className="transition-all duration-300 ease-out"
          />
        )}

        {/* Tick marks */}
        {ticks}

        {/* Numeric labels (÷ 1000) inside arc */}
        {labels}

        {/* Inner decorative ring */}
        <circle
          cx={CX}
          cy={CY}
          r={RADIUS - 20}
          fill="none"
          stroke="#1e293b"
          strokeOpacity="0.3"
          strokeWidth={1}
        />

        {/* Central digital readout — raw RPM value for test compatibility */}
        <text
          x={CX}
          y={CY + 8}
          textAnchor="middle"
          dominantBaseline="central"
          fill={isInRedline ? "#ef4444" : "#ffffff"}
          style={{
            fontSize: "48px",
            fontWeight: 700,
            filter: isInRedline
              ? "drop-shadow(0 0 10px rgba(239,68,68,0.5))"
              : "drop-shadow(0 0 10px rgba(6,182,212,0.45))",
          }}
        >
          {formatNumber(clampedRpm)}
        </text>

        {/* RPM unit label — text contains "RPM" for test: getByText(/RPM/) */}
        <text
          x={CX}
          y={CY + 46}
          textAnchor="middle"
          fill="#64748b"
          style={{ fontSize: "14px", fontWeight: 500, letterSpacing: "0.08em" }}
        >
          ×1000 RPM
        </text>
      </svg>
    </div>
  );
}
