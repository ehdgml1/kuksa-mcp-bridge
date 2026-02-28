/**
 * Tests for the ToolCallCard component.
 */

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ToolCallCard } from "../../src/components/chat/ToolCallCard";
import type { ToolCallInfo } from "../../src/types/chat";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTool(overrides: Partial<ToolCallInfo> = {}): ToolCallInfo {
  return {
    name: "get_vehicle_signal",
    args: {},
    status: "calling",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ToolCallCard", () => {
  it("renders the tool name", () => {
    render(<ToolCallCard toolCall={makeTool({ name: "diagnose_dtc" })} />);
    expect(screen.getByText("diagnose_dtc")).toBeInTheDocument();
  });

  it("shows '호출 중...' status text for calling status", () => {
    render(<ToolCallCard toolCall={makeTool({ status: "calling" })} />);
    expect(screen.getByText("호출 중...")).toBeInTheDocument();
  });

  it("does not show '호출 중...' for done status", () => {
    render(
      <ToolCallCard toolCall={makeTool({ status: "done", result: "ok" })} />,
    );
    expect(screen.queryByText("호출 중...")).not.toBeInTheDocument();
  });

  it("renders the checkmark SVG path for done status", () => {
    const { container } = render(
      <ToolCallCard toolCall={makeTool({ status: "done", result: "ok" })} />,
    );
    const checkPath = container.querySelector(
      'path[d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"]',
    );
    expect(checkPath).toBeInTheDocument();
  });

  it("renders the error (X) SVG path for error status", () => {
    const { container } = render(
      <ToolCallCard toolCall={makeTool({ status: "error", result: "failed" })} />,
    );
    const errorPath = container.querySelector(
      'path[d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"]',
    );
    expect(errorPath).toBeInTheDocument();
  });

  it("shows the result preview text for done status", () => {
    render(
      <ToolCallCard
        toolCall={makeTool({ status: "done", result: "speed: 80 km/h" })}
      />,
    );
    expect(screen.getByText("speed: 80 km/h")).toBeInTheDocument();
  });

  it("shows error result text for error status", () => {
    render(
      <ToolCallCard
        toolCall={makeTool({ status: "error", result: "Connection refused" })}
      />,
    );
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
  });

  it("truncates long result preview to 120 characters with ellipsis", () => {
    const longResult = "x".repeat(200);
    render(
      <ToolCallCard toolCall={makeTool({ status: "done", result: longResult })} />,
    );
    const expected = "x".repeat(120) + "...";
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it("expands the result when the card is clicked on done status", () => {
    const result = "full result content";
    render(
      <ToolCallCard toolCall={makeTool({ status: "done", result })} />,
    );

    const card = screen.getByRole("button");
    fireEvent.click(card);

    // After expand, result should appear inside a <pre> element
    const pre = document.querySelector("pre");
    expect(pre?.textContent).toBe(result);
  });

  it("calling status card does not have button role", () => {
    render(<ToolCallCard toolCall={makeTool({ status: "calling" })} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
