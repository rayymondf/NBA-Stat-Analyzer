import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import PlayerProfile from "./PlayerProfile";

vi.mock("../lib/api", () => ({
  api: {
    meta: vi.fn().mockResolvedValue({ current_season: "2024-25", seasons: ["2023-24", "2024-25"], season_types: ["Regular Season", "Playoffs"] }),
    summary: vi.fn().mockResolvedValue({ name: "Test Player", headshot: "headshot.jpg", team_name: "Test Team", team_id: null, jersey: "1", position: "G", age: 25, height: "6-4", experience: 3, season: "2024-25", season_type: "Regular Season", blurb: "Profile note", stats: { per_game: { PTS: 20, REB: 5, AST: 6 }, shooting: { TS_PCT: .6 } } }),
  },
}));
vi.mock("../components/profile/OverviewSection", () => ({ default: () => <div>Overview content</div> }));
vi.mock("../components/profile/ShootingSection", () => ({ default: () => <div>Shooting content</div> }));
vi.mock("../components/profile/EfficiencySection", () => ({ default: () => <div>Efficiency content</div> }));
vi.mock("../components/profile/PlaytimeSection", () => ({ default: () => <div>Playtime content</div> }));
vi.mock("../components/profile/FoulsSection", () => ({ default: () => <div>Fouls content</div> }));
vi.mock("../components/profile/GameLogSection", () => ({ default: () => <div>Games content</div> }));
vi.mock("../components/profile/TrendsSection", () => ({ default: () => <div>Trends content</div> }));
vi.mock("../components/profile/ImpactSection", () => ({ default: () => <div>Impact content</div> }));

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
afterEach(cleanup);
function renderProfile(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/player/:id" element={<><PlayerProfile /><Location /></>} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("PlayerProfile URL state", () => {
  it("restores a valid section and season context from the URL", async () => {
    renderProfile("/player/7?tab=shooting&season=2024-25&season_type=Playoffs&quarter=4&result=made");
    expect(await screen.findByText("Shooting content")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Season" })).toHaveValue("2024-25");
    expect(screen.getByRole("combobox", { name: "More analysis" })).toHaveValue("");
  });

  it("rejects unknown query values and writes selected analysis back to the URL", async () => {
    const user = userEvent.setup();
    renderProfile("/player/7?tab=unknown&season=not-a-season&per_mode=invalid");
    expect(await screen.findByText("Overview content")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Overview" }).find((button) => button.getAttribute("aria-current") === "page")).toBeDefined();
    await user.selectOptions(screen.getByRole("combobox", { name: "More analysis" }), "impact");
    expect(await screen.findByText("Impact content")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("tab=impact");
  });

  it("keeps advanced game filters in a disclosed panel and can reset them", async () => {
    const user = userEvent.setup();
    renderProfile("/player/7?location=home&last_n=5");
    await screen.findByText("Overview content");
    const disclosure = screen.getByText(/Advanced game filters/);
    await user.click(disclosure);
    await user.click(screen.getByRole("button", { name: "Reset filters" }));
    expect(screen.getByTestId("location")).not.toHaveTextContent("location=");
    expect(screen.getByTestId("location")).not.toHaveTextContent("last_n=");
  });
});
