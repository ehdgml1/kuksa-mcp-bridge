/**
 * React context for sharing Kuksa Databroker connection state.
 *
 * Wraps the useKuksaWebSocket hook and provides vehicle signal
 * data to the entire component tree.
 */

import { createContext, type ReactNode } from "react";
import type { ConnectionState, VssSignalData } from "../types/vss";
import { useKuksaWebSocket } from "../hooks/useKuksaWebSocket";

/** Shape of the Kuksa context value. */
export interface KuksaContextValue {
  /** Current WebSocket connection state */
  readonly connectionState: ConnectionState;
  /** Last error message, or null */
  readonly error: string | null;
  /** Map of VSS path → latest signal data */
  readonly signals: ReadonlyMap<string, VssSignalData>;
  /** Send an actuator set command */
  readonly setActuator: (path: string, value: number | string | boolean) => void;
}

/** React context for Kuksa Databroker data. */
export const KuksaContext = createContext<KuksaContextValue | null>(null);

/** Props for KuksaProvider. */
interface KuksaProviderProps {
  /** Child components to provide context to */
  readonly children: ReactNode;
  /** Optional WebSocket URL override (for testing) */
  readonly wsUrl?: string;
}

/**
 * Provider component that manages the Kuksa WebSocket connection.
 *
 * Wrap your application with this component to enable all child
 * components to access vehicle signal data via useSignal hook.
 */
export function KuksaProvider({ children, wsUrl }: KuksaProviderProps): React.ReactElement {
  const kuksaState = useKuksaWebSocket(wsUrl);

  return (
    <KuksaContext.Provider value={kuksaState}>
      {children}
    </KuksaContext.Provider>
  );
}
