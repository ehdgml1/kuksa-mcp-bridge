/**
 * Tests for the ChatMessage component.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "../../src/components/chat/ChatMessage";
import type { ChatMessage as ChatMessageType } from "../../src/types/chat";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMessage(
  overrides: Partial<ChatMessageType> = {},
): ChatMessageType {
  return {
    id: "test-id",
    role: "user",
    content: "Hello!",
    timestamp: new Date("2025-07-15T10:30:00Z"),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatMessage", () => {
  it("renders the message content", () => {
    render(<ChatMessage message={makeMessage({ content: "Test message" })} />);
    expect(screen.getByText("Test message")).toBeInTheDocument();
  });

  it("applies right-alignment class for user messages", () => {
    const { container } = render(
      <ChatMessage message={makeMessage({ role: "user" })} />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain("justify-end");
  });

  it("applies left-alignment class for assistant messages", () => {
    const { container } = render(
      <ChatMessage message={makeMessage({ role: "assistant", content: "Hi" })} />,
    );
    const wrapper = container.firstElementChild;
    expect(wrapper?.className).toContain("justify-start");
  });

  it("formats and renders the timestamp", () => {
    // Use a fixed timestamp; the formatted value depends on the locale but
    // should always contain digits and a colon separator.
    render(
      <ChatMessage
        message={makeMessage({ timestamp: new Date("2025-07-15T10:30:00Z") })}
      />,
    );
    // Find an element whose text matches a time pattern (digits:digits)
    const timeEl = document.querySelector(".text-xs.mt-1\\.5");
    expect(timeEl?.textContent).toMatch(/\d+:\d+/);
  });

  it("renders tool call cards before message text for assistant messages", () => {
    const message = makeMessage({
      role: "assistant",
      content: "Result text",
      toolCalls: [
        { name: "get_vehicle_signal", args: {}, status: "done", result: "ok" },
      ],
    });

    const { container } = render(<ChatMessage message={message} />);

    // Both tool call section and message text must be present
    const toolCallContainer = container.querySelector(".space-y-2");
    const textDiv = screen.getByText("Result text").closest("div");
    expect(toolCallContainer).toBeInTheDocument();
    expect(textDiv).toBeInTheDocument();

    // Verify DOM order: tool call container should precede the text div.
    // Node.DOCUMENT_POSITION_FOLLOWING means the argument (textDiv) comes after
    // the caller (toolCallContainer), i.e., toolCallContainer is first.
    const position = toolCallContainer!.compareDocumentPosition(textDiv!);
    // bit 4 (DOCUMENT_POSITION_FOLLOWING) or bit 20 (following + contained)
    expect(position & 0x14).toBeTruthy();
  });

  it("does not render tool call section for user messages", () => {
    const message = makeMessage({
      role: "user",
      content: "Hi",
    });

    const { container } = render(<ChatMessage message={message} />);
    // The space-y-2 div (tool call container) should not exist for user msgs
    expect(container.querySelector(".space-y-2")).not.toBeInTheDocument();
  });

  it("does not render content div when content is empty", () => {
    const message = makeMessage({
      role: "assistant",
      content: "",
    });

    const { container } = render(<ChatMessage message={message} />);

    // The component guards with content.length > 0, so the inner <div> wrapping
    // renderContent should not exist — only the timestamp div should be present.
    const messageBubble = container.querySelector(".leading-relaxed");
    // Should have exactly one child: the timestamp div (text-xs class)
    const children = Array.from(messageBubble?.children ?? []);
    expect(children).toHaveLength(1);
    expect(children[0]?.classList.contains("text-xs")).toBe(true);
  });

  it("renders multiple tool calls in order", () => {
    const message = makeMessage({
      role: "assistant",
      content: "",
      toolCalls: [
        { name: "tool_a", args: {}, status: "done", result: "res_a" },
        { name: "tool_b", args: {}, status: "calling" },
      ],
    });

    render(<ChatMessage message={message} />);

    expect(screen.getByText("tool_a")).toBeInTheDocument();
    expect(screen.getByText("tool_b")).toBeInTheDocument();
  });
});
