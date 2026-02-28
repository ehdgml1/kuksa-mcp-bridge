/**
 * Tests for the AiChatPanel component.
 *
 * The useAgentChat hook is mocked so that these tests focus exclusively
 * on rendering and UI interaction rather than SSE streaming logic.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AiChatPanel } from "../../src/components/chat/AiChatPanel";
import type { UseAgentChatResult } from "../../src/hooks/useAgentChat";

// ---------------------------------------------------------------------------
// Mock useAgentChat
// ---------------------------------------------------------------------------

const mockSendMessage = vi.fn();
const mockClearMessages = vi.fn();

const defaultHookState: UseAgentChatResult = {
  messages: [],
  isStreaming: false,
  error: null,
  sendMessage: mockSendMessage,
  clearMessages: mockClearMessages,
};

vi.mock("../../src/hooks/useAgentChat", () => ({
  useAgentChat: () => defaultHookState,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AiChatPanel", () => {
  it("renders without crashing", () => {
    const { container } = render(<AiChatPanel />);
    expect(container.firstChild).not.toBeNull();
  });

  it("shows 'AI Assistant' header text", () => {
    render(<AiChatPanel />);
    expect(screen.getByText("AI Assistant")).toBeInTheDocument();
  });

  it("shows welcome message when there are no messages", () => {
    render(<AiChatPanel />);
    expect(screen.getByText("AI Vehicle Assistant")).toBeInTheDocument();
  });

  it("shows descriptive subtitle in the empty state", () => {
    render(<AiChatPanel />);
    expect(
      screen.getByText("자연어로 차량 상태를 조회하고 제어할 수 있습니다."),
    ).toBeInTheDocument();
  });

  it("renders four quick suggestion buttons when chat is empty", () => {
    render(<AiChatPanel />);
    expect(screen.getByRole("button", { name: "차량 상태 점검" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "엔진 진단" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "에어컨 24도로 설정" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "배터리 상태 확인" })).toBeInTheDocument();
  });

  it("calls sendMessage with the correct message when a quick suggestion is clicked", () => {
    render(<AiChatPanel />);

    fireEvent.click(screen.getByRole("button", { name: "차량 상태 점검" }));

    expect(mockSendMessage).toHaveBeenCalledWith(
      "차량 전반적인 상태를 점검해주세요.",
    );
  });

  it("does not show the clear button when there are no messages", () => {
    render(<AiChatPanel />);
    expect(
      screen.queryByRole("button", { name: "Clear chat" }),
    ).not.toBeInTheDocument();
  });
});
