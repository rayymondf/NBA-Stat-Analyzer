import { afterEach, describe, expect, it, vi } from "vitest";
import { api, DATASET_URL } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("typed API client", () => {
  it("uses the versioned API and encodes query filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await api.search("Shai Gilgeous-Alexander");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/players/search?q=Shai%20Gilgeous-Alexander",
    );
    expect(DATASET_URL).toBe("/api/v1/ml/dataset.csv");
  });

  it("omits empty filters and surfaces problem details", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "season is invalid",
    }), { status: 422, headers: { "Content-Type": "application/problem+json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.games({ season: "", team: undefined })).rejects.toThrow("season is invalid");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/games");
  });

  it("posts structured AI requests", async () => {
    const report = {
      answer_markdown: "Grounded", verdict: null, key_findings: [],
      counterevidence: [], data_scope: {}, links: [],
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(report), {
      status: 200, headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.ask({ question: "Who leads?", mode: "auto" })).resolves.toEqual(report);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/ai/ask", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }));
  });

  it("covers every typed endpoint wrapper without leaking transport details", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({}), {
        status: 200, headers: { "Content-Type": "application/json" },
      }),
    ));
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([
      api.meta(), api.summary(1), api.overview(1), api.shooting(1),
      api.shotQuality(1), api.efficiency(1), api.playtime(1), api.fouls(1),
      api.gamelog(1), api.gameDetail(1, "0022500001"), api.trends(1),
      api.career(1), api.impact(1), api.compare(1, 2), api.modelInfo(),
      api.games(), api.investigate("0022500001"), api.leaders(), api.similar(1),
    ]);

    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toContain("/api/v1/compare?a=1&b=2");
    expect(urls).toContain("/api/v1/players/1/games/0022500001");
  });

  it("uses a generic status error when a problem body is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json", { status: 503 })));
    await expect(api.meta()).rejects.toThrow("Request failed (503)");
  });

  it("surfaces AI problem responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "AI quota exhausted",
    }), { status: 429, headers: { "Content-Type": "application/problem+json" } })));
    await expect(api.ask({ question: "Who leads?" })).rejects.toThrow("AI quota exhausted");
  });
});
