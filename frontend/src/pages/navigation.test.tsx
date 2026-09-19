import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import AiMode from "./AiMode";
import GamesPage from "./Games";
import { api } from "../lib/api";

function renderPage(node: React.ReactNode, entries: string[] | Array<{ pathname: string; state?: unknown }>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={entries}>{node}</MemoryRouter></QueryClientProvider>);
}

function Location() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

afterEach(() => vi.restoreAllMocks());

Object.defineProperty(Element.prototype, "scrollIntoView", { value: vi.fn(), writable: true });

describe("page navigation contracts", () => {
  it("restores valid Games filters from the URL and writes filter changes back", async () => {
    vi.spyOn(api, "meta").mockResolvedValue({ current_season: "2025-26", seasons: ["2024-25", "2025-26"], season_types: [], data_through: null, player_lookup_note: "", freshness_note: "" });
    vi.spyOn(api, "games").mockResolvedValue([]);
    renderPage(<><GamesPage /><Location /></>, ["/games?season=2024-25&type=Playoffs&team=BOS&date=2025-01-20"]);
    await waitFor(() => expect((screen.getByRole("combobox", { name: "Season" }) as HTMLSelectElement).value).toBe("2024-25"));
    expect((screen.getByRole("combobox", { name: "Season type" }) as HTMLSelectElement).value).toBe("Playoffs");
    expect((screen.getByRole("combobox", { name: "Team" }) as HTMLSelectElement).value).toBe("BOS");
    expect(screen.getByLabelText("Game date")).toHaveValue("2025-01-20");
    fireEvent.change(screen.getByRole("combobox", { name: "Team" }), { target: { value: "LAL" } });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("team=LAL"));
  });

  it("prefills an AI question from navigation without submitting it", async () => {
    const ask = vi.spyOn(api, "ask").mockResolvedValue({ answer_markdown: "", verdict: null, key_findings: [], counterevidence: [], data_scope: {}, links: [] });
    renderPage(<AiMode />, [{ pathname: "/ai", state: { question: "Why did Boston lose?", context: { game_id: "1" } } }]);
    expect(await screen.findByLabelText("Ask the analyst")).toHaveValue("Why did Boston lose?");
    expect(ask).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Who are the top five scorers/i }));
    expect(screen.getByLabelText("Ask the analyst")).toHaveValue("Who are the top five scorers in the NBA this season?");
    expect(ask).not.toHaveBeenCalled();
  });
});
