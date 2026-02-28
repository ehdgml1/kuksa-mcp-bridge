/**
 * Engine coolant temperature panel component.
 *
 * Renders a 270-degree arc gauge with three visible color zones
 * (green / amber / red) matching the automotive cluster aesthetic.
 * A thin value arc fills from the start to the current temperature,
 * with a glow whose color tracks the active zone.
 */

import { describeArc, valueToAngle } from "../gauges/GaugeUtils";

/** Props for the EngineTemp component. */
interface EngineTempProps {
  /** Engine coolant temperature in Celsius */
  readonly temperature: number;
}

// Gauge geometry constants
const CX = 70;
const CY = 70;
const RADIUS = 55;
const START_ANGLE = 135;
const END_ANGLE = 405;
const MAX_TEMP = 150;

// Zone thresholds
const WARN_TEMP = 100;
const OVERHEAT_TEMP = 110;

/**
 * Determine gauge glow/value color based on temperature.
 *
 * @param temp - Temperature in Celsius
 * @returns CSS hex color string
 */
function getTempColor(temp: number): string {
  if (temp > OVERHEAT_TEMP) return "#ef4444";
  if (temp > WARN_TEMP) return "#f59e0b";
  return "#06b6d4";
}

/**
 * Get human-readable temperature status label.
 *
 * @param temp - Temperature in Celsius
 * @returns Status label string
 */
function getTempStatus(temp: number): string {
  if (temp > OVERHEAT_TEMP) return "OVERHEAT";
  if (temp > WARN_TEMP) return "WARNING";
  return "NORMAL";
}

/**
 * Engine coolant temperature display with 270-degree arc gauge.
 *
 * Features three permanently visible zone arcs (green / amber / red)
 * that give immediate context even before the engine warms up.
 * A bright value arc with zone-matching glow fills to the current
 * temperature. Pulses red when overheating.
 */
export function EngineTemp({
  temperature,
}: EngineTempProps): React.ReactElement {
  const clampedTemp = Math.max(0, Math.min(MAX_TEMP, temperature));
  const fillColor = getTempColor(clampedTemp);
  const status = getTempStatus(clampedTemp);
  const isOverheat = clampedTemp > OVERHEAT_TEMP;

  // Zone boundary angles
  const greenEndAngle = valueToAngle(WARN_TEMP, 0, MAX_TEMP, START_ANGLE, END_ANGLE);
  const amberEndAngle = valueToAngle(OVERHEAT_TEMP, 0, MAX_TEMP, START_ANGLE, END_ANGLE);

  // Zone arc path descriptors (always visible background zones)
  const greenZoneArc = describeArc(CX, CY, RADIUS, START_ANGLE, greenEndAngle);
  const amberZoneArc = describeArc(CX, CY, RADIUS, greenEndAngle, amberEndAngle);
  const redZoneArc = describeArc(CX, CY, RADIUS, amberEndAngle, END_ANGLE);

  // Active value arc
  const valueAngle = valueToAngle(clampedTemp, 0, MAX_TEMP, START_ANGLE, END_ANGLE);
  const valueArc = describeArc(CX, CY, RADIUS, START_ANGLE, valueAngle);

  return (
    <div className={`glass-card p-3 flex flex-col overflow-hidden min-h-0 ${isOverheat ? "pulse-critical" : ""}`}>
      {/* Section title */}
      <h3 className="text-ivi-muted text-xs font-semibold uppercase tracking-wider mb-3">
        Engine Temp
      </h3>

      {/* Arc gauge + center readout */}
      <div className="flex justify-center mb-1 flex-1 min-h-0">
        <svg
          viewBox="0 0 140 140"
          className="w-32 h-32 max-h-full"
          aria-label={`Engine temperature ${clampedTemp.toFixed(0)}°C ${status}`}
        >
          <defs>
            {/* Glow filter keyed to current zone color */}
            <filter id="engtemp-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feFlood floodColor={fillColor} floodOpacity="0.5" result="color" />
              <feComposite in="color" in2="blur" operator="in" result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Zone arcs — tinted at low opacity so they always show context */}
          <path
            d={greenZoneArc}
            fill="none"
            stroke="#22c55e"
            strokeOpacity="0.2"
            strokeWidth={10}
            strokeLinecap="round"
          />
          <path
            d={amberZoneArc}
            fill="none"
            stroke="#f59e0b"
            strokeOpacity="0.2"
            strokeWidth={10}
            strokeLinecap="round"
          />
          <path
            d={redZoneArc}
            fill="none"
            stroke="#ef4444"
            strokeOpacity="0.2"
            strokeWidth={10}
            strokeLinecap="round"
          />

          {/* Value arc with zone-matching glow */}
          {clampedTemp > 0 && (
            <path
              d={valueArc}
              fill="none"
              stroke={fillColor}
              strokeWidth={10}
              strokeLinecap="round"
              filter="url(#engtemp-glow)"
              className="transition-all duration-500 ease-out"
            />
          )}

          {/* Temperature number */}
          <text
            x={CX}
            y={CY - 4}
            textAnchor="middle"
            dominantBaseline="central"
            fill="white"
            style={{ fontSize: "34px", fontWeight: 700, letterSpacing: "-0.5px" }}
          >
            {clampedTemp.toFixed(0)}
          </text>

          {/* Unit */}
          <text
            x={CX}
            y={CY + 22}
            textAnchor="middle"
            dominantBaseline="central"
            fill="#9ca3af"
            style={{ fontSize: "14px", fontWeight: 400 }}
          >
            °C
          </text>

          {/* Status label */}
          <text
            x={CX}
            y={CY + 40}
            textAnchor="middle"
            dominantBaseline="central"
            fill={fillColor}
            style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "1px" }}
          >
            {status}
          </text>
        </svg>
      </div>
    </div>
  );
}
