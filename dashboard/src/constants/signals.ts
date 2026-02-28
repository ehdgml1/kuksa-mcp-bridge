/**
 * VSS signal path constants and gauge configuration.
 *
 * Centralizes all VSS paths used by the dashboard and
 * defines threshold configuration for gauge rendering.
 */

/** All VSS paths subscribed by the dashboard. */
export const VSS_PATHS = {
  SPEED: "Vehicle.Speed",
  TRAVELED_DISTANCE: "Vehicle.TraveledDistance",
  ENGINE_RPM: "Vehicle.Powertrain.CombustionEngine.Speed",
  ENGINE_COOLANT_TEMP: "Vehicle.Powertrain.CombustionEngine.ECT",
  HVAC_DRIVER_TEMP: "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature",
  AMBIENT_TEMP: "Vehicle.Cabin.HVAC.AmbientAirTemperature",
  BATTERY_SOC: "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
  BATTERY_VOLTAGE: "Vehicle.Powertrain.TractionBattery.CurrentVoltage",
  BATTERY_TEMP: "Vehicle.Powertrain.TractionBattery.Temperature.Average",
  DTC_LIST: "Vehicle.OBD.DTCList",
} as const;

/** Array of all VSS paths for bulk subscription. */
export const ALL_VSS_PATHS: readonly string[] = Object.values(VSS_PATHS);

/** Speedometer gauge thresholds. */
export const SPEED_CONFIG = {
  min: 0,
  max: 200,
  unit: "km/h",
  warningThreshold: 160,
  dangerThreshold: 180,
} as const;

/** RPM gauge thresholds. */
export const RPM_CONFIG = {
  min: 0,
  max: 8000,
  unit: "RPM",
  redlineRpm: 6500,
} as const;

/** Engine coolant temperature thresholds. */
export const ENGINE_TEMP_CONFIG = {
  min: 0,
  max: 150,
  unit: "°C",
  normalMax: 100,
  warningMax: 110,
} as const;

/** Battery SOC thresholds. */
export const BATTERY_CONFIG = {
  criticalThreshold: 10,
  lowThreshold: 20,
  mediumThreshold: 50,
} as const;

/** HVAC temperature range. */
export const HVAC_CONFIG = {
  minTemp: 16,
  maxTemp: 30,
  step: 0.5,
  unit: "°C",
} as const;

/** WebSocket reconnection configuration. */
export const RECONNECT_CONFIG = {
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  multiplier: 2,
} as const;
