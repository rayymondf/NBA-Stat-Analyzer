import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  AnimatedNumber, Card, CardTitle, EmptyState, ErrorState, GlossaryTip,
  HowItsMade, PageHeader, PercentileBar, Segmented, Skeleton, SkeletonCard,
  StatTile,
} from "./ui";

describe("shared UI contracts", () => {
  it("renders page and state components accessibly", () => {
    render(
      <>
        <PageHeader kicker="Model" title="Shot quality" dek="Calibrated predictions" />
        <Card><StatTile label="Brier" value="0.224" /></Card>
        <ErrorState message="Upstream unavailable" />
        <EmptyState message="No games" />
      </>,
    );
    expect(screen.getByRole("heading", { name: "Shot quality" })).toBeInTheDocument();
    expect(screen.getByText("Upstream unavailable")).toBeInTheDocument();
    expect(screen.getByText("No games")).toBeInTheDocument();
  });

  it("emits the selected typed segment", () => {
    const onChange = vi.fn();
    render(<Segmented
      options={[{ value: "actual", label: "Actual" }, { value: "expected", label: "Expected" }]}
      value="actual"
      onChange={onChange}
    />);
    fireEvent.click(screen.getByRole("button", { name: "Expected" }));
    expect(onChange).toHaveBeenCalledWith("expected");
  });

  it("shows glossary content on focus", () => {
    render(<GlossaryTip term="TS_PCT" />);
    const button = screen.getByRole("button", { name: /What is TS_PCT/i });
    fireEvent.focus(button);
    expect(screen.getByText(/True shooting/i)).toBeInTheDocument();
  });

  it("expands implementation notes and renders supporting primitives", () => {
    render(
      <>
        <HowItsMade>Computed from official game logs.</HowItsMade>
        <CardTitle tip="TS_PCT">Efficiency</CardTitle>
        <PercentileBar label="Points" value="25.0" percentile={83} poolLabel="guards" />
        <Skeleton className="h-2" />
        <SkeletonCard lines={2} />
      </>,
    );
    expect(screen.queryByText("Computed from official game logs.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /How this is made/i }));
    expect(screen.getByText("Computed from official game logs.")).toBeInTheDocument();
    expect(screen.getByText("83rd")).toBeInTheDocument();
  });

  it("renders glossary labels and missing glossary terms safely", () => {
    const { rerender } = render(<GlossaryTip term="TS_PCT" label="True shooting" />);
    expect(screen.getByText("True shooting")).toBeInTheDocument();
    rerender(<GlossaryTip term="NOT_A_TERM" label="Unknown" />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("animates numbers and supports reduced motion", async () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    });
    render(<AnimatedNumber value={42} format={(value) => value.toFixed(0)} />);
    expect(await screen.findByText("42")).toBeInTheDocument();
  });
});
