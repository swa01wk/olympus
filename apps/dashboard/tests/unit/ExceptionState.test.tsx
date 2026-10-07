import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExceptionState } from "@/components/truth/ExceptionState";

describe("ExceptionState", () => {
  it("renders reason, consequence, and action", () => {
    render(
      <ExceptionState
        status="stale"
        reason="Stream disconnected"
        consequence="Refetch before commands."
        action={{ label: "Refetch", onClick: vi.fn() }}
      />,
    );
    expect(screen.getByText("Stream disconnected")).toBeInTheDocument();
    expect(screen.getByText(/Refetch before commands/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refetch" })).toBeInTheDocument();
  });
});
