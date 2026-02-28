/**
 * Tests for the BatteryStatus component.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BatteryStatus } from "../../src/components/panels/BatteryStatus";

describe("BatteryStatus", () => {
  it("renders SOC percentage", () => {
    render(<BatteryStatus soc={75} voltage={400} temperature={25} />);
    expect(screen.getByText("75")).toBeInTheDocument();
    expect(screen.getByText("%")).toBeInTheDocument();
  });

  it("renders voltage", () => {
    render(<BatteryStatus soc={50} voltage={392.5} temperature={30} />);
    expect(screen.getByText(/392\.5/)).toBeInTheDocument();
  });

  it("renders temperature", () => {
    render(<BatteryStatus soc={50} voltage={400} temperature={28.3} />);
    expect(screen.getByText(/28\.3/)).toBeInTheDocument();
  });
});
