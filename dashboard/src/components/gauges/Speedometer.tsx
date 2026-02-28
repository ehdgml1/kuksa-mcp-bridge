/**
 * Automotive cluster-style circular speedometer gauge.
 *
 * Renders a 270-degree neon arc gauge with per-zone glow filters,
 * tick marks, and a large digital readout — no needle. Visual style
 * matches Hyundai Ioniq 5 / Mercedes EQS instrument cluster.
 */

import { describeArc, polarToCartesian, valueToAngle, formatNumber } from "./GaugeUtils";

/** Props for the Speedometer component. */
interface SpeedometerProps {
  /** Current speed in km/h */
  readonly speed: number;
  /** Maximum speed for gauge scale (default: 200) */
  readonly maxSpeed?: number;
  /** Speed threshold for warning color (default: 160) */
  readonly warningThreshold?: number;
  /** Speed threshold for danger color (default: 180) */
  readonly dangerThreshold?: number;
}

// Gauge geometry constants — 270-degree arc centered in 300×300 viewBox
const CX = 150;
const CY = 150;
const RADIUS = 120;
const START_ANGLE = 135;
const END_ANGLE = 405;
const TICK_OUTER = 120;
const TICK_INNER_MAJOR = 104;
const TICK_INNER_MINOR = 111;

/** Speed values where numeric labels are drawn inside the arc. */
const TICK_LABELS = [0, 40, 80, 120, 160, 200];

/**
 * Resolve the SVG glow filter URL based on current speed thresholds.
 *
 * @param speed - Current speed value
 * @param warning - Warning threshold
 * @param danger - Danger threshold
 * @returns SVG filter reference string
 */
function getGlowFilter(speed: number, warning: number, danger: number): string {
  if (speed >= danger) return "url(#speed-glow-red)";
  if (speed >= warning) return "url(#speed-glow-amber)";
  return "url(#speed-glow-cyan)";
}

/**
 * Resolve the stroke color of the value arc based on speed thresholds.
 *
 * @param speed - Current speed value
 * @param warning - Warning threshold
 * @param danger - Danger threshold
 * @returns Hex color string
 */
function getArcColor(speed: number, warning: number, danger: number): string {
  if (speed >= danger) return "#ef4444";
  if (speed >= warning) return "#f59e0b";
  return "#06b6d4";
}

/**
 * Automotive cluster-style circular speedometer — no needle.
 *
 * A 270-degree neon glow arc fills from 0 to the current speed.
 * The arc color transitions through cyan → amber → red as speed
 * crosses warning and danger thresholds. Fine and major tick marks
 * ring the gauge; numeric labels sit inside the arc at every 40 km/h.
 */
export function Speedometer({
  speed,
  maxSpeed = 200,
  warningThreshold = 160,
  dangerThreshold = 180,
}: SpeedometerProps): React.ReactElement {
  const clampedSpeed = Math.max(0, Math.min(maxSpeed, speed));
  const valueEndAngle = valueToAngle(clampedSpeed, 0, maxSpeed, START_ANGLE, END_ANGLE);
  const backgroundArc = describeArc(CX, CY, RADIUS, START_ANGLE, END_ANGLE);
  const valueArc = describeArc(CX, CY, RADIUS, START_ANGLE, valueEndAngle);
  const arcColor = getArcColor(clampedSpeed, warningThreshold, dangerThreshold);
  const glowFilter = getGlowFilter(clampedSpeed, warningThreshold, dangerThreshold);

  // Build fine (every 10 km/h) and major (every 40 km/h) tick marks
  const ticks: React.ReactElement[] = [];
  for (let i = 0; i <= maxSpeed; i += 10) {
    const angle = valueToAngle(i, 0, maxSpeed, START_ANGLE, END_ANGLE);
    const isMajor = i % 40 === 0;
    const outer = polarToCartesian(CX, CY, TICK_OUTER, angle);
    const inner = polarToCartesian(CX, CY, isMajor ? TICK_INNER_MAJOR : TICK_INNER_MINOR, angle);

    ticks.push(
      <line
        key={`speed-tick-${i}`}
        x1={outer.x}
        y1={outer.y}
        x2={inner.x}
        y2={inner.y}
        stroke={isMajor ? "#94a3b8" : "#334155"}
        strokeWidth={isMajor ? 2 : 1}
        strokeLinecap="round"
      />,
    );
  }

  // Labels positioned inside the arc at every 40 km/h
  const labels = TICK_LABELS.map((value) => {
    const angle = valueToAngle(value, 0, maxSpeed, START_ANGLE, END_ANGLE);
    const pos = polarToCartesian(CX, CY, RADIUS - 26, angle);
    return (
      <text
        key={`speed-label-${value}`}
        x={pos.x}
        y={pos.y}
        textAnchor="middle"
        dominantBaseline="central"
        fill="#64748b"
        style={{ fontSize: "11px", fontWeight: 500 }}
      >
        {value}
      </text>
    );
  });

  return (
    <div className="glass-card p-3 flex flex-col overflow-hidden min-h-0">
      <svg viewBox="0 0 300 300" className="w-full flex-1 min-h-0">
        <defs>
          {/* Cyan glow — normal speed zone */}
          <filter id="speed-glow-cyan" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood floodColor="#06b6d4" floodOpacity="0.6" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Amber glow — warning zone */}
          <filter id="speed-glow-amber" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood floodColor="#f59e0b" floodOpacity="0.6" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Red glow — danger zone */}
          <filter id="speed-glow-red" x="-50%" y="-50%" width="200%" height="200%">
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

        {/* Value arc — neon glow fill from start to current speed */}
        {clampedSpeed > 0 && (
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

        {/* Numeric labels inside arc */}
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

        {/*
         * Central digital readout.
         * fontSize kept at 42px to satisfy test: querySelector('text[style*="font-size: 42px"]')
         */}
        <text
          x={CX}
          y={CY + 8}
          textAnchor="middle"
          dominantBaseline="central"
          fill="#ffffff"
          style={{
            fontSize: "42px",
            fontWeight: 700,
            filter: "drop-shadow(0 0 10px rgba(6,182,212,0.45))",
          }}
        >
          {formatNumber(clampedSpeed)}
        </text>

        {/* Speed unit label */}
        <text
          x={CX}
          y={CY + 46}
          textAnchor="middle"
          fill="#64748b"
          style={{ fontSize: "14px", fontWeight: 500, letterSpacing: "0.08em" }}
        >
          km/h
        </text>
      </svg>
    </div>
  );
}
