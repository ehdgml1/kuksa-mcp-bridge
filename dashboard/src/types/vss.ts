/**
 * VSS (Vehicle Signal Specification) type definitions.
 *
 * Defines TypeScript interfaces for vehicle signal data
 * and the VISS v2 WebSocket protocol messages.
 */

/** Parsed value from a VSS signal. */
export type VssValue = number | string | boolean | null;

/** Single vehicle signal data point. */
export interface VssSignalData {
  /** VSS path (e.g., "Vehicle.Speed") */
  readonly path: string;
  /** Parsed signal value */
  readonly value: VssValue;
  /** ISO 8601 timestamp from the databroker */
  readonly timestamp: string;
}

/** WebSocket connection lifecycle state. */
export type ConnectionState = "connected" | "disconnected" | "reconnecting";

// --- VISS v2 Protocol Message Types ---

/** Base request structure for VISS v2 messages. */
export interface VissRequestBase {
  readonly requestId: string;
}

/** VISS v2 get request. */
export interface VissGetRequest extends VissRequestBase {
  readonly action: "get";
  readonly path: string;
}

/** VISS v2 set request. */
export interface VissSetRequest extends VissRequestBase {
  readonly action: "set";
  readonly path: string;
  readonly value: string;
}

/** VISS v2 subscribe request. */
export interface VissSubscribeRequest extends VissRequestBase {
  readonly action: "subscribe";
  readonly path: string;
}

/** VISS v2 unsubscribe request. */
export interface VissUnsubscribeRequest extends VissRequestBase {
  readonly action: "unsubscribe";
  readonly subscriptionId: string;
}

/** Union of all VISS v2 request types. */
export type VissRequest =
  | VissGetRequest
  | VissSetRequest
  | VissSubscribeRequest
  | VissUnsubscribeRequest;

/** Successful VISS v2 get/set response. */
export interface VissSuccessResponse {
  readonly requestId: string;
  readonly action: "get" | "set";
  readonly path: string;
  readonly value?: string;
  readonly timestamp?: string;
}

/** VISS v2 subscribe acknowledgement. */
export interface VissSubscribeResponse {
  readonly requestId: string;
  readonly action: "subscribe";
  readonly subscriptionId: string;
  readonly timestamp?: string;
}

/** VISS v2 subscription event (pushed update). */
export interface VissSubscriptionEvent {
  readonly action: "subscription";
  readonly subscriptionId: string;
  readonly data: {
    readonly path: string;
    readonly dp: {
      readonly value: string;
      readonly ts: string;
    };
  };
}

/** VISS v2 error response. */
export interface VissErrorResponse {
  readonly requestId?: string;
  readonly action: string;
  readonly error: {
    readonly number: number;
    readonly reason: string;
    readonly message: string;
  };
}

/** Union of all incoming VISS v2 messages. */
export type VissResponse =
  | VissSuccessResponse
  | VissSubscribeResponse
  | VissSubscriptionEvent
  | VissErrorResponse;

/** Callback invoked when a signal value is updated. */
export type SignalUpdateCallback = (path: string, data: VssSignalData) => void;

/** Callback invoked when connection state changes. */
export type ConnectionChangeCallback = (state: ConnectionState) => void;

/** Callback invoked on WebSocket errors. */
export type ErrorCallback = (error: string) => void;
