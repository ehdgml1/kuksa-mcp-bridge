/**
 * Tests for the useKuksaWebSocket hook.
 */

import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKuksaWebSocket } from "../../src/hooks/useKuksaWebSocket";

describe("useKuksaWebSocket", () => {
  it("returns disconnected state initially", () => {
    // Note: state quickly transitions to reconnecting once connect() is called
    const { result } = renderHook(() => useKuksaWebSocket("ws://localhost:9999"));
    // Should be either disconnected or reconnecting initially
    expect(["disconnected", "reconnecting"]).toContain(result.current.connectionState);
  });

  it("returns empty signals map initially", () => {
    const { result } = renderHook(() => useKuksaWebSocket("ws://localhost:9999"));
    expect(result.current.signals.size).toBe(0);
  });

  it("provides a setActuator function", () => {
    const { result } = renderHook(() => useKuksaWebSocket("ws://localhost:9999"));
    expect(typeof result.current.setActuator).toBe("function");
  });
});
