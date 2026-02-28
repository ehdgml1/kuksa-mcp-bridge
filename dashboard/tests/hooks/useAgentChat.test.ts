/**
 * Tests for the useAgentChat hook.
 *
 * Tests helper logic (parseSSELine, buildHistory) by accessing
 * them via the exported hook interface and by inspecting hook state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAgentChat } from "../../src/hooks/useAgentChat";

// ---------------------------------------------------------------------------
// parseSSELine — tested indirectly via a minimal fetch mock that feeds lines
// ---------------------------------------------------------------------------

/**
 * Build a minimal ReadableStream that emits one chunk then closes.
 */
function makeStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const text = lines.join("\n") + "\n";
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function makeOkResponse(stream: ReadableStream<Uint8Array>): Response {
  return new Response(stream, { status: 200 });
}

describe("useAgentChat — initial state", () => {
  it("starts with empty messages array", () => {
    const { result } = renderHook(() => useAgentChat());
    expect(result.current.messages).toHaveLength(0);
  });

  it("starts with isStreaming false", () => {
    const { result } = renderHook(() => useAgentChat());
    expect(result.current.isStreaming).toBe(false);
  });

  it("starts with null error", () => {
    const { result } = renderHook(() => useAgentChat());
    expect(result.current.error).toBeNull();
  });

  it("exposes sendMessage and clearMessages functions", () => {
    const { result } = renderHook(() => useAgentChat());
    expect(typeof result.current.sendMessage).toBe("function");
    expect(typeof result.current.clearMessages).toBe("function");
  });
});

describe("useAgentChat — parseSSELine behaviour (via streaming)", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("ignores non-data lines and [DONE] sentinel, accumulates text_chunk events", async () => {
    const lines = [
      ": comment line",
      "",
      "data: [DONE]",
      `data: ${JSON.stringify({ type: "text_chunk", content: "hello" })}`,
      `data: ${JSON.stringify({ type: "done" })}`,
    ];

    vi.mocked(fetch).mockResolvedValue(makeOkResponse(makeStream(lines)));

    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      result.current.sendMessage("test");
      // Give the async stream processing time to complete
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    expect(assistantMsg?.content).toBe("hello");
  });

  it("ignores lines with invalid JSON after 'data: ' prefix", async () => {
    const lines = [
      "data: {bad json}",
      `data: ${JSON.stringify({ type: "text_chunk", content: "ok" })}`,
      `data: ${JSON.stringify({ type: "done" })}`,
    ];

    vi.mocked(fetch).mockResolvedValue(makeOkResponse(makeStream(lines)));

    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      result.current.sendMessage("test");
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    const assistantMsg = result.current.messages.find(
      (m) => m.role === "assistant",
    );
    // Invalid JSON is skipped; only the valid text_chunk is applied
    expect(assistantMsg?.content).toBe("ok");
  });
});

describe("useAgentChat — buildHistory behaviour (via sendMessage)", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("filters messages with empty content from the history sent to the API", async () => {
    // Seed an assistant message that has empty content (e.g., mid-stream)
    // by completing one exchange first, then checking what history the next
    // request carries.
    const doneLine = `data: ${JSON.stringify({ type: "done" })}`;
    vi.mocked(fetch).mockResolvedValue(
      makeOkResponse(makeStream([doneLine])),
    );

    const { result } = renderHook(() => useAgentChat());

    // First message — assistant response will be empty (no text_chunk events)
    await act(async () => {
      result.current.sendMessage("hello");
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // Reset mock and capture the body of the second request
    interface CapturedBody {
      message: string;
      history: Array<{ role: string; content: string }>;
    }
    let capturedBody: CapturedBody | null = null;
    vi.mocked(fetch).mockImplementation(async (_url, options) => {
      capturedBody = JSON.parse((options?.body as string) ?? "{}") as CapturedBody;
      return makeOkResponse(makeStream([doneLine]));
    });

    await act(async () => {
      result.current.sendMessage("second message");
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    // The empty-content assistant message should be filtered out
    const historyContents = capturedBody?.history.map((h) => h.content) ?? [];
    expect(historyContents).not.toContain("");
  });
});

describe("useAgentChat — clearMessages", () => {
  it("resets messages, isStreaming, and error to initial values", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      makeOkResponse(
        makeStream([`data: ${JSON.stringify({ type: "done" })}`]),
      ),
    );

    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      result.current.sendMessage("hello");
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    expect(result.current.messages.length).toBeGreaterThan(0);

    act(() => {
      result.current.clearMessages();
    });

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.error).toBeNull();

    vi.restoreAllMocks();
  });
});
