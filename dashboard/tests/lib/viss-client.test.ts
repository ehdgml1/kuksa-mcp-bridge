/**
 * Tests for the VISS v2 WebSocket client.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { VissClient, parseVissValue } from "../../src/lib/viss-client";
import { MockWebSocket } from "../setup";

describe("parseVissValue", () => {
  it("parses numeric strings to numbers", () => {
    expect(parseVissValue("120.5")).toBe(120.5);
    expect(parseVissValue("0")).toBe(0);
    expect(parseVissValue("-10")).toBe(-10);
  });

  it("parses boolean strings", () => {
    expect(parseVissValue("true")).toBe(true);
    expect(parseVissValue("false")).toBe(false);
  });

  it("returns null for empty/null/undefined", () => {
    expect(parseVissValue(null)).toBeNull();
    expect(parseVissValue(undefined)).toBeNull();
    expect(parseVissValue("")).toBeNull();
  });

  it("returns string for non-numeric strings", () => {
    expect(parseVissValue("P0301,P0420")).toBe("P0301,P0420");
  });
});

describe("VissClient", () => {
  let client: VissClient;
  let onSignalUpdate: ReturnType<typeof vi.fn>;
  let onConnectionChange: ReturnType<typeof vi.fn>;
  let onError: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.clearInstances();
    onSignalUpdate = vi.fn();
    onConnectionChange = vi.fn();
    onError = vi.fn();
    client = new VissClient({
      url: "ws://localhost:8090",
      onSignalUpdate,
      onConnectionChange,
      onError,
    });
  });

  afterEach(() => {
    client.disconnect();
    vi.useRealTimers();
  });

  it("creates WebSocket with correct URL", () => {
    client.connect();
    const ws = MockWebSocket.getLastInstance();
    expect(ws?.url).toBe("ws://localhost:8090");
  });

  it("transitions to connected on open", () => {
    client.connect();
    const ws = MockWebSocket.getLastInstance();
    ws?.simulateOpen();
    expect(onConnectionChange).toHaveBeenCalledWith("connected");
  });

  it("sends subscribe message in VISS v2 format", () => {
    client.connect();
    const ws = MockWebSocket.getLastInstance();
    ws?.simulateOpen();
    const sendSpy = vi.spyOn(ws!, "send");
    client.subscribe(["Vehicle.Speed"]);

    expect(sendSpy).toHaveBeenCalledTimes(1);
    const msg = JSON.parse(sendSpy.mock.calls[0]![0] as string);
    expect(msg.action).toBe("subscribe");
    expect(msg.path).toBe("Vehicle.Speed");
    expect(msg.requestId).toBeDefined();
  });

  it("parses subscription events", () => {
    client.connect();
    const ws = MockWebSocket.getLastInstance();
    ws?.simulateOpen();

    ws?.simulateMessage({
      action: "subscription",
      subscriptionId: "sub-1",
      data: {
        path: "Vehicle.Speed",
        dp: { value: "120.5", ts: "2025-01-01T00:00:00Z" },
      },
    });

    expect(onSignalUpdate).toHaveBeenCalledWith("Vehicle.Speed", {
      path: "Vehicle.Speed",
      value: 120.5,
      timestamp: "2025-01-01T00:00:00Z",
    });
  });

  it("schedules reconnect on unexpected close", () => {
    client.connect();
    const ws = MockWebSocket.getLastInstance();
    ws?.simulateOpen();
    ws?.simulateClose();

    expect(onConnectionChange).toHaveBeenCalledWith("reconnecting");
  });

  it("sends set command with string value", () => {
    client.connect();
    const ws = MockWebSocket.getLastInstance();
    ws?.simulateOpen();
    const sendSpy = vi.spyOn(ws!, "send");

    client.set("Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature", 24);

    const msg = JSON.parse(sendSpy.mock.calls[0]![0] as string);
    expect(msg.action).toBe("set");
    expect(msg.path).toBe("Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature");
    expect(msg.value).toBe("24");
  });
});
