import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/primitives/StatusBadge";

describe("StatusBadge", () => {
  it("renders glyph and label for blocked status", () => {
    render(<StatusBadge status="blocked" />);
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("⊘")).toBeInTheDocument();
  });
});
