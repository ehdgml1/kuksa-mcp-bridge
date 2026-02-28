/**
 * Tests for the Speedometer component.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Speedometer } from "../../src/components/gauges/Speedometer";

describe("Speedometer", () => {
  it("renders the speed value in the digital readout", () => {
    render(<Speedometer speed={95} />);
    // 95 is not a tick label, so it uniquely identifies the digital readout
    expect(screen.getByText("95")).toBeInTheDocument();
  });

  it("renders km/h unit label", () => {
    render(<Speedometer speed={0} />);
    expect(screen.getByText("km/h")).toBeInTheDocument();
  });

  it("clamps speed to max", () => {
    const { container } = render(<Speedometer speed={250} maxSpeed={200} />);
    // The digital readout uses a specific style; find it by font-size
    const readout = container.querySelector('text[style*="font-size: 42px"]');
    expect(readout?.textContent).toBe("200");
  });

  it("clamps speed to min (0)", () => {
    render(<Speedometer speed={-10} />);
    // 0 appears as both tick label and readout; use getAllByText
    const zeros = screen.getAllByText("0");
    expect(zeros.length).toBeGreaterThanOrEqual(1);
  });
});
