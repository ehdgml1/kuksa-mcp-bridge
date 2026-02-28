/**
 * Tests for the HvacPanel component.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HvacPanel } from "../../src/components/panels/HvacPanel";

describe("HvacPanel", () => {
  it("renders ambient temperature", () => {
    render(
      <HvacPanel ambientTemp={26.5} targetTemp={24.0} onTargetTempChange={vi.fn()} />,
    );
    expect(screen.getByText("26.5")).toBeInTheDocument();
  });

  it("renders target temperature", () => {
    render(
      <HvacPanel ambientTemp={26.5} targetTemp={24.0} onTargetTempChange={vi.fn()} />,
    );
    expect(screen.getByText("24.0")).toBeInTheDocument();
  });

  it("calls onTargetTempChange with increased value on + click", () => {
    const onChange = vi.fn();
    render(
      <HvacPanel ambientTemp={26.5} targetTemp={24.0} onTargetTempChange={onChange} />,
    );
    fireEvent.click(screen.getByLabelText("Increase temperature"));
    expect(onChange).toHaveBeenCalledWith(24.5);
  });

  it("calls onTargetTempChange with decreased value on - click", () => {
    const onChange = vi.fn();
    render(
      <HvacPanel ambientTemp={26.5} targetTemp={24.0} onTargetTempChange={onChange} />,
    );
    fireEvent.click(screen.getByLabelText("Decrease temperature"));
    expect(onChange).toHaveBeenCalledWith(23.5);
  });
});
