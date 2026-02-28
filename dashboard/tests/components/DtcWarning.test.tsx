/**
 * Tests for the DtcWarning component.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DtcWarning } from "../../src/components/warnings/DtcWarning";

describe("DtcWarning", () => {
  it("renders nothing when no DTC codes", () => {
    const { container } = render(<DtcWarning dtcCodes={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders DTC codes when present", () => {
    render(<DtcWarning dtcCodes={["P0301", "P0420"]} />);
    expect(screen.getByText("P0301")).toBeInTheDocument();
    expect(screen.getByText("P0420")).toBeInTheDocument();
  });

  it("displays check engine header", () => {
    render(<DtcWarning dtcCodes={["P0301"]} />);
    expect(screen.getByText("Check Engine")).toBeInTheDocument();
  });

  it("shows correct count text for single code", () => {
    render(<DtcWarning dtcCodes={["P0301"]} />);
    expect(screen.getByText("1 active code")).toBeInTheDocument();
  });

  it("shows correct count text for multiple codes", () => {
    render(<DtcWarning dtcCodes={["P0301", "P0420"]} />);
    expect(screen.getByText("2 active codes")).toBeInTheDocument();
  });
});
