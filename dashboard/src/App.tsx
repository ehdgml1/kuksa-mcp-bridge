/**
 * Root application component for the IVI Dashboard.
 *
 * Integrates the Kuksa WebSocket provider with all dashboard
 * components, wiring each gauge and panel to its corresponding
 * VSS signal path.
 */

import { useCallback, useContext } from "react";
import { KuksaProvider, KuksaContext } from "./context/KuksaContext";
import type { KuksaContextValue } from "./context/KuksaContext";
import { VSS_PATHS } from "./constants/signals";
import { DashboardLayout, StatusBar } from "./components/layout/DashboardLayout";
import { ConnectionBadge } from "./components/status/ConnectionBadge";
import { Speedometer } from "./components/gauges/Speedometer";
import { RpmGauge } from "./components/gauges/RpmGauge";
import { BatteryStatus } from "./components/panels/BatteryStatus";
import { EngineTemp } from "./components/panels/EngineTemp";
import { HvacPanel } from "./components/panels/HvacPanel";
import { DtcWarning } from "./components/warnings/DtcWarning";
import { AiChatPanel } from "./components/chat/AiChatPanel";

/**
 * Extract a numeric signal value with fallback.
 *
 * @param signals - Signal data map
 * @param path - VSS signal path
 * @param fallback - Default value if signal not available
 * @returns Numeric signal value
 */
function getNumericSignal(
  signals: ReadonlyMap<string, { value: number | string | boolean | null }>,
  path: string,
  fallback: number = 0,
): number {
  const data = signals.get(path);
  if (data?.value === null || data?.value === undefined) return fallback;
  return typeof data.value === "number" ? data.value : fallback;
}

/**
 * Parse DTC list from signal value.
 *
 * The simulator sends DTCs as a comma-separated string.
 *
 * @param signals - Signal data map
 * @returns Array of DTC code strings
 */
function parseDtcList(
  signals: ReadonlyMap<string, { value: number | string | boolean | null }>,
): string[] {
  const data = signals.get(VSS_PATHS.DTC_LIST);
  if (!data?.value || typeof data.value !== "string") return [];
  return data.value
    .split(",")
    .map((code) => code.trim())
    .filter((code) => code.length > 0);
}

/**
 * Dashboard content with live signal data.
 *
 * Reads from KuksaContext and distributes values
 * to individual gauge and panel components.
 */
function DashboardContent(): React.ReactElement {
  const context = useContext(KuksaContext) as KuksaContextValue;
  const { signals, connectionState, error, setActuator } = context;

  const speed = getNumericSignal(signals, VSS_PATHS.SPEED);
  const rpm = getNumericSignal(signals, VSS_PATHS.ENGINE_RPM);
  const batterySoc = getNumericSignal(signals, VSS_PATHS.BATTERY_SOC, 100);
  const batteryVoltage = getNumericSignal(signals, VSS_PATHS.BATTERY_VOLTAGE, 400);
  const batteryTemp = getNumericSignal(signals, VSS_PATHS.BATTERY_TEMP, 25);
  const engineTemp = getNumericSignal(signals, VSS_PATHS.ENGINE_COOLANT_TEMP, 90);
  const ambientTemp = getNumericSignal(signals, VSS_PATHS.AMBIENT_TEMP, 22);
  const targetTemp = getNumericSignal(signals, VSS_PATHS.HVAC_DRIVER_TEMP, 22);
  const dtcCodes = parseDtcList(signals);

  const handleTargetTempChange = useCallback(
    (temp: number) => {
      setActuator(VSS_PATHS.HVAC_DRIVER_TEMP, temp);
    },
    [setActuator],
  );

  return (
    <>
      <ConnectionBadge state={connectionState} error={error} />
      <DashboardLayout
        chatPanel={<AiChatPanel />}
        statusBar={<StatusBar connectionState={connectionState} error={error} />}
      >
        <Speedometer speed={speed} />
        <RpmGauge rpm={rpm} />
        <BatteryStatus soc={batterySoc} voltage={batteryVoltage} temperature={batteryTemp} />
        <EngineTemp temperature={engineTemp} />
        <HvacPanel
          ambientTemp={ambientTemp}
          targetTemp={targetTemp}
          onTargetTempChange={handleTargetTempChange}
        />
        <DtcWarning dtcCodes={dtcCodes} />
      </DashboardLayout>
    </>
  );
}

/**
 * Root App component.
 *
 * Wraps the dashboard in the KuksaProvider for
 * WebSocket connectivity to the Kuksa Databroker.
 */
export function App(): React.ReactElement {
  return (
    <KuksaProvider>
      <DashboardContent />
    </KuksaProvider>
  );
}
