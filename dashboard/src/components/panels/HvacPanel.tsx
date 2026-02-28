/**
 * HVAC control panel component.
 *
 * Displays ambient cabin temperature and provides interactive
 * target temperature controls with heating/cooling mode indicators.
 * Styled as an automotive-grade climate control panel using
 * glassmorphism cards and touch-friendly controls.
 */

import { HVAC_CONFIG } from "../../constants/signals";

/** Props for the HvacPanel component. */
interface HvacPanelProps {
  /** Current ambient/cabin temperature in Celsius */
  readonly ambientTemp: number;
  /** Current HVAC target temperature in Celsius */
  readonly targetTemp: number;
  /** Callback when target temperature is changed */
  readonly onTargetTempChange: (temp: number) => void;
}

/**
 * Snowflake SVG icon for active cooling mode.
 *
 * Rendered in cyan when target temperature is below cabin temperature.
 */
function SnowflakeIcon(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-10 h-10 fill-gauge-cyan"
      aria-hidden="true"
    >
      <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z" />
    </svg>
  );
}

/**
 * Flame SVG icon for active heating mode.
 *
 * Rendered in red-orange when target temperature exceeds cabin temperature.
 */
function FlameIcon(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-10 h-10 fill-gauge-red"
      aria-hidden="true"
    >
      <path d="M13.5 0.67s0.74 2.65 0.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z" />
    </svg>
  );
}

/**
 * Neutral checkmark icon shown when target and cabin temperatures match.
 *
 * Rendered in muted color when the HVAC system is at equilibrium.
 */
function NeutralIcon(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-10 h-10 fill-ivi-muted opacity-40"
      aria-hidden="true"
    >
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
    </svg>
  );
}

/**
 * Thermometer SVG icon for the cabin temperature display.
 */
function ThermometerIcon(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-5 h-5 fill-ivi-muted"
      aria-hidden="true"
    >
      <path d="M15 13V5c0-1.66-1.34-3-3-3S9 3.34 9 5v8c-1.21.91-2 2.37-2 4 0 2.76 2.24 5 5 5s5-2.24 5-5c0-1.63-.79-3.09-2-4zm-4-8c0-.55.45-1 1-1s1 .45 1 1v8h-2V5z" />
    </svg>
  );
}

/**
 * Target crosshair SVG icon for the target temperature display.
 */
function TargetIcon(): React.ReactElement {
  return (
    <svg
      viewBox="0 0 24 24"
      className="w-5 h-5 fill-gauge-cyan opacity-70"
      aria-hidden="true"
    >
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm0-14c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm0-6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
    </svg>
  );
}

/**
 * HVAC climate control panel.
 *
 * Full-width glassmorphism card with two sections: cabin temperature
 * on the left and adjustable target temperature on the right, separated
 * by a prominent mode icon. Features automotive-style 48px circular
 * touch controls with cyan glow on the active target temperature.
 *
 * Temperature adjustment uses HVAC_CONFIG.step (0.5°C) per tap,
 * clamped to HVAC_CONFIG.minTemp / HVAC_CONFIG.maxTemp.
 */
export function HvacPanel({
  ambientTemp,
  targetTemp,
  onTargetTempChange,
}: HvacPanelProps): React.ReactElement {
  const isCooling = targetTemp < ambientTemp;
  const isHeating = targetTemp > ambientTemp;

  /**
   * Increment target temperature by one step.
   *
   * Clamps at HVAC_CONFIG.maxTemp to prevent out-of-range values.
   */
  function handleIncrease(): void {
    const next = Math.min(HVAC_CONFIG.maxTemp, targetTemp + HVAC_CONFIG.step);
    onTargetTempChange(next);
  }

  /**
   * Decrement target temperature by one step.
   *
   * Clamps at HVAC_CONFIG.minTemp to prevent out-of-range values.
   */
  function handleDecrease(): void {
    const next = Math.max(HVAC_CONFIG.minTemp, targetTemp - HVAC_CONFIG.step);
    onTargetTempChange(next);
  }

  return (
    <div className="glass-card p-3 overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 mb-4">
        {isCooling ? (
          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-gauge-cyan" aria-hidden="true">
            <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z" />
          </svg>
        ) : isHeating ? (
          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-gauge-red" aria-hidden="true">
            <path d="M13.5 0.67s0.74 2.65 0.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z" />
          </svg>
        ) : null}
        <h3 className="text-ivi-muted text-xs font-semibold uppercase tracking-widest">
          Climate Control
        </h3>
      </div>

      {/* ── Main body: three columns ────────────────────────────── */}
      <div className="flex items-center justify-between gap-3">

        {/* Left section — Cabin temperature (read-only) */}
        <div className="flex-1 flex flex-col items-center gap-1.5">
          <div className="flex items-center gap-1.5 mb-0.5">
            <ThermometerIcon />
            <span className="text-ivi-muted text-xs font-medium uppercase tracking-wider">
              Cabin
            </span>
          </div>
          <p className="font-instrument text-[2rem] font-bold leading-none text-ivi-text/70">
            {ambientTemp.toFixed(1)}
            <span className="text-sm text-ivi-muted ml-1 font-normal">°C</span>
          </p>
        </div>

        {/* Center section — Mode icon */}
        <div className="flex flex-col items-center justify-center px-2">
          {isCooling ? (
            <SnowflakeIcon />
          ) : isHeating ? (
            <FlameIcon />
          ) : (
            <NeutralIcon />
          )}
        </div>

        {/* Right section — Target temperature with controls */}
        <div className="flex-1 flex flex-col items-center gap-1.5">
          <div className="flex items-center gap-1.5 mb-0.5">
            <TargetIcon />
            <span className="text-ivi-muted text-xs font-medium uppercase tracking-wider">
              Target
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* Decrease button */}
            <button
              type="button"
              onClick={handleDecrease}
              disabled={targetTemp <= HVAC_CONFIG.minTemp}
              className="w-12 h-12 rounded-full glass-card-highlight
                         flex items-center justify-center
                         text-xl font-bold text-ivi-text
                         hover:bg-white/[0.1] hover:border-gauge-cyan
                         active:scale-95
                         disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all duration-150"
              aria-label="Decrease temperature"
            >
              −
            </button>

            {/* Target temp value */}
            <p className="font-instrument text-[2rem] font-bold leading-none text-gauge-cyan glow-text-cyan min-w-[4.5rem] text-center">
              {targetTemp.toFixed(1)}
              <span className="text-sm text-ivi-muted ml-1 font-normal">°C</span>
            </p>

            {/* Increase button */}
            <button
              type="button"
              onClick={handleIncrease}
              disabled={targetTemp >= HVAC_CONFIG.maxTemp}
              className="w-12 h-12 rounded-full glass-card-highlight
                         flex items-center justify-center
                         text-xl font-bold text-ivi-text
                         hover:bg-white/[0.1] hover:border-gauge-cyan
                         active:scale-95
                         disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all duration-150"
              aria-label="Increase temperature"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* ── Temperature delta bar ───────────────────────────────── */}
      {(isCooling || isHeating) && (
        <div className="mt-4 h-px w-full relative overflow-hidden rounded-full">
          <div
            className={`absolute inset-0 rounded-full opacity-40 ${
              isCooling
                ? "bg-gradient-to-r from-gauge-cyan/0 via-gauge-cyan to-gauge-cyan/0"
                : "bg-gradient-to-r from-gauge-red/0 via-gauge-red to-gauge-red/0"
            }`}
          />
        </div>
      )}
    </div>
  );
}
