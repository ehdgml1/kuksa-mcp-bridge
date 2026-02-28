/**
 * VISS v2 WebSocket client for Eclipse Kuksa Databroker.
 *
 * Framework-agnostic client implementing the VISS v2 JSON
 * protocol with automatic reconnection and subscription
 * management.
 */

import type {
  ConnectionChangeCallback,
  ConnectionState,
  ErrorCallback,
  SignalUpdateCallback,
  VissResponse,
  VssSignalData,
} from "../types/vss";
import { RECONNECT_CONFIG } from "../constants/signals";

/** Configuration for the VISS client. */
export interface VissClientConfig {
  /** WebSocket URL (e.g., "ws://localhost:8090") */
  readonly url: string;
  /** Called when a subscribed signal updates */
  readonly onSignalUpdate: SignalUpdateCallback;
  /** Called when connection state changes */
  readonly onConnectionChange: ConnectionChangeCallback;
  /** Called on WebSocket or protocol errors */
  readonly onError: ErrorCallback;
}

/** Tracked subscription for auto-resubscribe on reconnect. */
interface ActiveSubscription {
  readonly path: string;
  subscriptionId: string | null;
}

/**
 * Parse a VISS string value to a typed JavaScript value.
 *
 * VISS v2 transmits all values as strings. This function
 * attempts numeric and boolean parsing before falling back
 * to the raw string.
 */
export function parseVissValue(raw: unknown): number | string | boolean | null {
  if (raw === undefined || raw === null || raw === "") {
    return null;
  }

  // Already a primitive — return directly
  if (typeof raw === "number") return raw;
  if (typeof raw === "boolean") return raw;

  // Coerce to string for further parsing
  const str = String(raw);

  // Boolean detection
  if (str === "true") return true;
  if (str === "false") return false;

  // Numeric detection
  const num = Number(str);
  if (!Number.isNaN(num) && str.trim() !== "") {
    return num;
  }

  return str;
}

/**
 * VISS v2 WebSocket client.
 *
 * Manages a WebSocket connection to Kuksa Databroker,
 * handles subscriptions, and auto-reconnects with
 * exponential backoff.
 */
export class VissClient {
  private ws: WebSocket | null = null;
  private requestIdCounter = 0;
  private connectionState: ConnectionState = "disconnected";
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay: number = RECONNECT_CONFIG.initialDelayMs;
  private subscriptions = new Map<string, ActiveSubscription>();
  private pendingRequests = new Map<string, (response: VissResponse) => void>();
  private intentionalClose = false;

  private readonly config: VissClientConfig;

  constructor(config: VissClientConfig) {
    this.config = config;
  }

  /** Current connection state. */
  get state(): ConnectionState {
    return this.connectionState;
  }

  /** Open WebSocket connection to the databroker. */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.intentionalClose = false;
    this.setConnectionState("reconnecting");

    try {
      this.ws = new WebSocket(this.config.url);
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
    } catch (err) {
      this.config.onError(`Failed to create WebSocket: ${String(err)}`);
      this.scheduleReconnect();
    }
  }

  /** Gracefully close the WebSocket connection. */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.subscriptions.clear();
    this.pendingRequests.clear();

    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.setConnectionState("disconnected");
  }

  /**
   * Subscribe to signal updates for the given paths.
   *
   * @param paths - Array of VSS paths to subscribe to
   */
  subscribe(paths: readonly string[]): void {
    for (const path of paths) {
      if (this.subscriptions.has(path)) {
        continue;
      }
      this.subscriptions.set(path, { path, subscriptionId: null });
      this.sendSubscribeRequest(path);
    }
  }

  /**
   * Unsubscribe from a specific signal path.
   *
   * @param path - VSS path to unsubscribe from
   */
  unsubscribe(path: string): void {
    const sub = this.subscriptions.get(path);
    if (!sub) return;

    if (sub.subscriptionId && this.ws?.readyState === WebSocket.OPEN) {
      const requestId = this.nextRequestId();
      this.send({
        action: "unsubscribe",
        subscriptionId: sub.subscriptionId,
        requestId,
      });
    }
    this.subscriptions.delete(path);
  }

  /**
   * Set an actuator value on the databroker.
   *
   * @param path - VSS actuator path
   * @param value - Value to set
   */
  set(path: string, value: number | string | boolean): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      this.config.onError("Cannot set value: not connected");
      return;
    }

    const requestId = this.nextRequestId();
    this.send({
      action: "set",
      path,
      value: String(value),
      requestId,
    });
  }

  // --- Private Methods ---

  private handleOpen(): void {
    this.reconnectDelay = RECONNECT_CONFIG.initialDelayMs;
    this.setConnectionState("connected");
    this.resubscribeAll();
  }

  private handleMessage(event: MessageEvent): void {
    let response: VissResponse;
    try {
      response = JSON.parse(String(event.data)) as VissResponse;
    } catch {
      this.config.onError("Failed to parse VISS message");
      return;
    }

    // Handle subscription events (pushed updates)
    if ("action" in response && response.action === "subscription") {
      const subEvent = response as Extract<VissResponse, { action: "subscription" }>;
      const signalData: VssSignalData = {
        path: subEvent.data.path,
        value: parseVissValue(subEvent.data.dp.value),
        timestamp: subEvent.data.dp.ts,
      };
      this.config.onSignalUpdate(signalData.path, signalData);
      return;
    }

    // Handle subscribe acknowledgements
    if ("action" in response && response.action === "subscribe" && "subscriptionId" in response) {
      const subResp = response as Extract<VissResponse, { action: "subscribe" }>;
      // Find the subscription by matching pending request
      for (const sub of this.subscriptions.values()) {
        if (sub.subscriptionId === null) {
          sub.subscriptionId = subResp.subscriptionId;
          break;
        }
      }
      return;
    }

    // Handle errors
    if ("error" in response) {
      const errResp = response as Extract<VissResponse, { error: unknown }>;
      this.config.onError(
        `VISS error ${errResp.error.number}: ${errResp.error.reason} - ${errResp.error.message}`,
      );
      return;
    }

    // Handle pending request callbacks
    if ("requestId" in response && response.requestId) {
      const callback = this.pendingRequests.get(response.requestId);
      if (callback) {
        this.pendingRequests.delete(response.requestId);
        callback(response);
      }
    }
  }

  private handleClose(): void {
    this.ws = null;

    if (!this.intentionalClose) {
      this.setConnectionState("reconnecting");
      this.scheduleReconnect();
    }
  }

  private handleError(): void {
    this.config.onError("WebSocket connection error");
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(
        this.reconnectDelay * RECONNECT_CONFIG.multiplier,
        RECONNECT_CONFIG.maxDelayMs,
      );
      this.connect();
    }, this.reconnectDelay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private resubscribeAll(): void {
    for (const sub of this.subscriptions.values()) {
      sub.subscriptionId = null;
      this.sendSubscribeRequest(sub.path);
    }
  }

  private sendSubscribeRequest(path: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return;

    const requestId = this.nextRequestId();
    this.send({
      action: "subscribe",
      path,
      requestId,
    });
  }

  private send(message: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  private nextRequestId(): string {
    this.requestIdCounter += 1;
    return `req-${this.requestIdCounter}`;
  }

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.config.onConnectionChange(state);
    }
  }
}
