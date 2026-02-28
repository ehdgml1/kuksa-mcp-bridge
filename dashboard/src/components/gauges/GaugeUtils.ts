/**
 * Pure utility functions for SVG gauge rendering.
 *
 * Provides mathematical helpers for converting values to
 * polar coordinates and SVG arc path descriptions.
 */

/** Point in 2D space. */
export interface Point {
  readonly x: number;
  readonly y: number;
}

/**
 * Convert polar coordinates to Cartesian (SVG) coordinates.
 *
 * @param cx - Center X coordinate
 * @param cy - Center Y coordinate
 * @param radius - Distance from center
 * @param angleDeg - Angle in degrees (0 = right, clockwise)
 * @returns Cartesian point
 */
export function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleDeg: number,
): Point {
  const angleRad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRad),
    y: cy + radius * Math.sin(angleRad),
  };
}

/**
 * Generate an SVG arc path descriptor.
 *
 * @param cx - Center X coordinate
 * @param cy - Center Y coordinate
 * @param radius - Arc radius
 * @param startAngle - Start angle in degrees
 * @param endAngle - End angle in degrees
 * @returns SVG path `d` attribute string
 */
export function describeArc(
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number,
): string {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? 0 : 1;

  return [
    "M", start.x, start.y,
    "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y,
  ].join(" ");
}

/**
 * Map a value to an angle within a gauge arc.
 *
 * @param value - Current value
 * @param min - Minimum value
 * @param max - Maximum value
 * @param startAngle - Start angle of the gauge arc (degrees)
 * @param endAngle - End angle of the gauge arc (degrees)
 * @returns Corresponding angle in degrees
 */
export function valueToAngle(
  value: number,
  min: number,
  max: number,
  startAngle: number,
  endAngle: number,
): number {
  const clamped = Math.max(min, Math.min(max, value));
  const ratio = (clamped - min) / (max - min);
  return startAngle + ratio * (endAngle - startAngle);
}

/**
 * Format a number for gauge display.
 *
 * @param value - Number to format
 * @param decimals - Decimal places (default 0)
 * @returns Formatted string
 */
export function formatNumber(value: number, decimals: number = 0): string {
  return value.toFixed(decimals);
}
