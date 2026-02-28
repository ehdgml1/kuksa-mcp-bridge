/**
 * Convenience hook for reading a single VSS signal.
 *
 * Reads from KuksaContext and returns the latest data
 * for the specified VSS path.
 */

import { useContext, useMemo } from "react";
import type { VssSignalData } from "../types/vss";
import { KuksaContext } from "../context/KuksaContext";

/**
 * Read a single signal value from the Kuksa context.
 *
 * @param path - VSS signal path (e.g., "Vehicle.Speed")
 * @returns Signal data or undefined if not yet received
 */
export function useSignal(path: string): VssSignalData | undefined {
  const context = useContext(KuksaContext);
  if (!context) {
    throw new Error("useSignal must be used within a KuksaProvider");
  }

  return useMemo(() => context.signals.get(path), [context.signals, path]);
}
