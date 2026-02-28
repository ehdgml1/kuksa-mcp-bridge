/**
 * Tests for the RpmGauge component.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RpmGauge } from "../../src/components/gauges/RpmGauge";

describe("RpmGauge", () => {
  it("renders RPM value", () => {
    render(<RpmGauge rpm={3000} />);
    expect(screen.getByText("3000")).toBeInTheDocument();
  });

  it("renders RPM unit label", () => {
    render(<RpmGauge rpm={0} />);
    expect(screen.getByText(/RPM/)).toBeInTheDocument();
  });

  it("clamps RPM to max", () => {
    render(<RpmGauge rpm={10000} maxRpm={8000} />);
    expect(screen.getByText("8000")).toBeInTheDocument();
  });
});
