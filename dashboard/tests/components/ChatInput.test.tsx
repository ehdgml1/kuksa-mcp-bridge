/**
 * Tests for the ChatInput component.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ChatInput } from "../../src/components/chat/ChatInput";

describe("ChatInput", () => {
  const onSend = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a textarea and a send button", () => {
    render(<ChatInput onSend={onSend} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send message" })).toBeInTheDocument();
  });

  it("send button is disabled when input is empty", () => {
    render(<ChatInput onSend={onSend} />);
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });

  it("send button becomes enabled when the user types text", () => {
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "hello" } });

    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
  });

  it("calls onSend with the trimmed text when Enter is pressed", () => {
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "  hello world  " } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).toHaveBeenCalledWith("hello world");
  });

  it("clears the textarea after sending via Enter", () => {
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(textarea).toHaveValue("");
  });

  it("does not call onSend on Shift+Enter (allows newline)", () => {
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "line1\nline2" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("calls onSend when the send button is clicked", () => {
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(onSend).toHaveBeenCalledWith("hello");
  });

  it("send button is disabled when the disabled prop is true", () => {
    render(<ChatInput onSend={onSend} disabled />);
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });

  it("does not call onSend via Enter when disabled prop is true", () => {
    render(<ChatInput onSend={onSend} disabled />);
    const textarea = screen.getByRole("textbox");

    // Simulate typing by changing value and pressing Enter while disabled
    fireEvent.change(textarea, { target: { value: "hello" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not call onSend when Enter is pressed on whitespace-only input", () => {
    render(<ChatInput onSend={onSend} />);
    const textarea = screen.getByRole("textbox");

    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    expect(onSend).not.toHaveBeenCalled();
  });
});
