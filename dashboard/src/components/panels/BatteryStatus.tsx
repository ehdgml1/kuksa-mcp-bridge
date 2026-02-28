/**
 * Battery status panel component.
 *
 * Displays state of charge as a 270-degree circular arc ring,
 * consistent with the main gauge aesthetic. Voltage and temperature
 * are shown in sub-boxes beneath the ring.
 */

import { describeArc, valueToAngle } from "../gauges/GaugeUtils";

/** Props for the BatteryStatus component. */
interface BatteryStatusProps {
  /** State of charge percentage (0-100) */
  readonly soc: number;
  /** Battery voltage in volts */
  readonly voltage: number;
  /** Battery temperature in Celsius */
  readonly temperature: number;
}

// Ring geometry constants
const CX = 80;
const CY = 80;
const RADIUS = 65;
const START_ANGLE = 135;
const END_ANGLE = 405;

/**
 * Determine ring color based on SOC level.
 *
 * @param soc - State of charge percentage (0-100)
 * @returns CSS hex color string
 */
function getBatteryColor(soc: number): string {
  if (soc <= 20) return "#ef4444";
  if (soc <= 50) return "#f59e0b";
  return "#22c55e";
}

/**
 * Battery status display with circular arc ring visualization.
 *
 * Shows a 270-degree SVG ring that fills proportionally to SOC,
 * colored green → amber → red as charge depletes. Pulses when
 * critically low (<10%). Voltage and temperature are shown in
 * glassmorphism sub-boxes below the ring.
 */
export function BatteryStatus({
  soc,
  voltage,
  temperature,
}: BatteryStatusProps): React.ReactElement {
  const clampedSoc = Math.max(0, Math.min(100, soc));
  const fillColor = getBatteryColor(clampedSoc);
  const isCritical = clampedSoc < 10;

  // Arc paths
  const bgArc = describeArc(CX, CY, RADIUS, START_ANGLE, END_ANGLE);
  const valueAngle = valueToAngle(clampedSoc, 0, 100, START_ANGLE, END_ANGLE);
  const valueArc = describeArc(CX, CY, RADIUS, START_ANGLE, valueAngle);

  return (
    <div className="glass-card p-3 flex flex-col overflow-hidden min-h-0">
      {/* Section title */}
      <h3 className="text-ivi-muted text-xs font-semibold uppercase tracking-wider mb-1">
        Battery
      </h3>

      {/* Circular ring + center readout */}
      <div className="flex justify-center mb-2 flex-1 min-h-0">
        <svg
          viewBox="0 0 160 160"
          className={`w-36 h-36 max-h-full ${isCritical ? "pulse-critical" : ""}`}
          aria-label={`Battery ${clampedSoc.toFixed(0)}%`}
        >
          <defs>
            {/* Glow filter for the value arc */}
            <filter id="battery-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feFlood floodColor={fillColor} floodOpacity="0.5" result="color" />
              <feComposite in="color" in2="blur" operator="in" result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background track arc */}
          <path
            d={bgArc}
            fill="none"
            stroke="#1e293b"
            strokeOpacity="0.7"
            strokeWidth={10}
            strokeLinecap="round"
          />

          {/* Value arc — only render when SOC > 0 */}
          {clampedSoc > 0 && (
            <path
              d={valueArc}
              fill="none"
              stroke={fillColor}
              strokeWidth={10}
              strokeLinecap="round"
              filter="url(#battery-glow)"
              className="transition-all duration-700 ease-out"
            />
          )}

          {/* Lightning bolt icon (small, above the number) */}
          <g transform="translate(72, 52)">
            <path
              d="M10 0 L4 8 L8 8 L6 16 L12 6 L8 6 Z"
              fill={fillColor}
              opacity="0.85"
            />
          </g>

          {/* SOC number — large and bold in the center */}
          <text
            x={CX}
            y={CY + 8}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            style={{ fontSize: "42px", fontWeight: 700, letterSpacing: "-1px" }}
          >
            {clampedSoc.toFixed(0)}
          </text>

          {/* Percent symbol — smaller and muted, offset right */}
          <text
            x={CX + 30}
            y={CY + 16}
            textAnchor="middle"
            dominantBaseline="central"
            fill="#9ca3af"
            style={{ fontSize: "18px", fontWeight: 500 }}
          >
            %
          </text>
        </svg>
      </div>

      {/* Voltage and Temperature sub-boxes */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white/[0.03] rounded-lg px-3 py-2">
          <p className="text-ivi-muted text-xs tracking-wide">Voltage</p>
          <p className="text-ivi-text text-sm font-semibold mt-0.5">
            {voltage.toFixed(1)}
            <span className="text-ivi-muted font-normal ml-1">V</span>
          </p>
        </div>
        <div className="bg-white/[0.03] rounded-lg px-3 py-2">
          <p className="text-ivi-muted text-xs tracking-wide">Temperature</p>
          <p className="text-ivi-text text-sm font-semibold mt-0.5">
            {temperature.toFixed(1)}
            <span className="text-ivi-muted font-normal ml-1">°C</span>
          </p>
        </div>
      </div>
    </div>
  );
}
