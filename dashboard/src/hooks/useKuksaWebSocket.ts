/**
 * React hook for managing Kuksa Databroker WebSocket connection.
 *
 * Creates a VissClient instance, subscribes to all configured
 * VSS paths, and batches signal updates via requestAnimationFrame.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ConnectionState, VssSignalData } from "../types/vss";
import { VissClient } from "../lib/viss-client";
import { ALL_VSS_PATHS } from "../constants/signals";

/** Return type of the useKuksaWebSocket hook. */
export interface UseKuksaWebSocketResult {
  /** Current WebSocket connection state */
  readonly connectionState: ConnectionState;
  /** Last error message, or null */
  readonly error: string | null;
  /** Map of VSS path → latest signal data */
  readonly signals: ReadonlyMap<string, VssSignalData>;
  /** Send an actuator set command */
  readonly setActuator: (path: string, value: number | string | boolean) => void;
}

/**
 * Hook that connects to Kuksa Databroker via VISS v2 WebSocket.
 *
 * @param wsUrl - WebSocket URL (defaults to env variable)
 * @returns Connection state, signal data, and actuator setter
 */
export function useKuksaWebSocket(
  wsUrl: string = import.meta.env.VITE_KUKSA_WS_URL || "ws://localhost:8090",
): UseKuksaWebSocketResult {
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [error, setError] = useState<string | null>(null);
  const [signals, setSignals] = useState<ReadonlyMap<string, VssSignalData>>(
    () => new Map<string, VssSignalData>(),
  );

  const clientRef = useRef<VissClient | null>(null);
  const pendingUpdatesRef = useRef<Map<string, VssSignalData>>(new Map());
  const rafRef = useRef<number | null>(null);

  // Flush batched signal updates
  const flushUpdates = useCallback(() => {
    rafRef.current = null;
    const pending = pendingUpdatesRef.current;
    if (pending.size === 0) return;

    const batch = new Map(pending);
    pending.clear();

    setSignals((prev) => {
      const next = new Map(prev);
      for (const [path, data] of batch) {
        next.set(path, data);
      }
      return next;
    });
  }, []);

  // Schedule batched update via requestAnimationFrame
  const scheduleFlush = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(flushUpdates);
    }
  }, [flushUpdates]);

  useEffect(() => {
    const client = new VissClient({
      url: wsUrl,
      onSignalUpdate: (path: string, data: VssSignalData) => {
        pendingUpdatesRef.current.set(path, data);
        scheduleFlush();
      },
      onConnectionChange: (state: ConnectionState) => {
        setConnectionState(state);
        if (state === "connected") {
          setError(null);
        }
      },
      onError: (errMsg: string) => {
        setError(errMsg);
      },
    });

    clientRef.current = client;
    client.connect();
    client.subscribe(ALL_VSS_PATHS);

    return () => {
      client.disconnect();
      clientRef.current = null;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [wsUrl, scheduleFlush]);

  const setActuator = useCallback(
    (path: string, value: number | string | boolean) => {
      clientRef.current?.set(path, value);
    },
    [],
  );

  return { connectionState, error, signals, setActuator };
}
