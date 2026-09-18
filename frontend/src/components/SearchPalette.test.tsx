import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type SearchResult } from "../lib/api";
import SearchPalette from "./SearchPalette";

const RESULT: SearchResult = {
  player_id: 201939,
  name: "Stephen Curry",
  team: "GSW",
  team_name: "Golden State Warriors",
  position: "G",
  jersey: "30",
  headshot: "/curry.png",
  ppg: 27.2,
  rpg: 4.5,
  apg: 6.1,
  lookup_season: "2025-26",
  has_season_stats: true,
  current_roster: true,
};

function renderPalette(props?: Partial<ComponentProps<typeof SearchPalette>>) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const onClose = vi.fn();
  const onPick = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SearchPalette open onClose={onClose} onPick={onPick} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onClose, onPick };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SearchPalette", () => {
  it("debounces, exposes combobox semantics, and supports keyboard selection", async () => {
    const search = vi.spyOn(api, "search").mockResolvedValue([RESULT]);
    const { onClose, onPick } = renderPalette();
    const input = screen.getByRole("combobox", { name: "Player name" });

    await userEvent.type(input, "Cur");
    expect(screen.getByText(/Waiting for you/)).toBeInTheDocument();
    await waitFor(() => expect(search).toHaveBeenCalledWith("Cur", expect.any(AbortSignal)));

    const option = await screen.findByRole("option", { name: /Stephen Curry/ });
    expect(option).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-expanded", "true");

    await userEvent.type(input, "{Enter}");
    expect(onPick).toHaveBeenCalledWith(201939, "Stephen Curry");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows request errors and closes on Escape", async () => {
    vi.spyOn(api, "search").mockRejectedValue(new Error("NBA search unavailable"));
    const { onClose } = renderPalette();
    const input = screen.getByRole("combobox");

    await userEvent.type(input, "Nope");
    expect(await screen.findByRole("alert")).toHaveTextContent("NBA search unavailable");
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
