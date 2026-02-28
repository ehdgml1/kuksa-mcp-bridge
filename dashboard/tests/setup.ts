/**
 * Vitest test setup file.
 *
 * Configures testing environment with DOM matchers
 * and global mocks for browser APIs.
 */

import "@testing-library/jest-dom/vitest";

// Mock WebSocket for all tests
class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  private static instances: MockWebSocket[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(_data: string): void {
    // No-op in mock
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
  }

  /** Simulate the connection opening. */
  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  /** Simulate receiving a message. */
  simulateMessage(data: unknown): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data) }));
  }

  /** Simulate connection closing. */
  simulateClose(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }

  /** Get the most recently created instance. */
  static getLastInstance(): MockWebSocket | undefined {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1];
  }

  /** Clear all tracked instances. */
  static clearInstances(): void {
    MockWebSocket.instances = [];
  }
}

// Assign to global
Object.assign(globalThis, { WebSocket: MockWebSocket, MockWebSocket });

// Declare for TypeScript
declare global {
  const MockWebSocket: typeof import("./setup").MockWebSocket;
}

export { MockWebSocket };
