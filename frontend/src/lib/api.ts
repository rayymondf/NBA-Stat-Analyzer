const BASE = "/api";

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const qs = params
    ? "?" +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const res = await fetch(`${BASE}${path}${qs}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export interface SearchResult {
  player_id: number;
  name: string;
  team: string | null;
  team_name: string | null;
  position: string | null;
  jersey: string | null;
  headshot: string;
  ppg: number | null;
  rpg: number | null;
  apg: number | null;
  lookup_season: string;
  has_season_stats: boolean;
  current_roster: boolean;
}

export interface Filters {
  season?: string;
  season_type?: string;
  location?: string;
  outcome?: string;
  starter?: boolean;
  last_n?: number;
  opponent?: string;
  date_from?: string;
  date_to?: string;
}

export interface Percentile {
  value: number;
  percentile: number;
  position_group: string;
  pool_size: number;
}

export interface ShotPoint {
  x: number;
  y: number;
  made: boolean;
  value: number;
  dist: number;
  game_id: string;
  date: string;
  period: number;
  action: string;
  zone: string;
  vs: string;
}

export interface Zone {
  zone: string;
  fga: number;
  fgm: number;
  pct: number | null;
  league_pct: number | null;
  diff: number | null;
  freq: number;
}

export const api = {
  meta: () =>
    get<{
      current_season: string;
      seasons: string[];
      season_types: string[];
      data_through: string | null;
      player_lookup_note: string;
      freshness_note: string;
    }>("/meta"),
  search: (q: string) => get<SearchResult[]>("/players/search", { q }),
  summary: (id: number, p?: Filters) => get<any>(`/players/${id}/summary`, p as any),
  overview: (id: number, p?: Filters) => get<any>(`/players/${id}/overview`, p as any),
  shooting: (id: number, p?: Record<string, unknown>) => get<any>(`/players/${id}/shooting`, p),
  efficiency: (id: number, p?: Filters) => get<any>(`/players/${id}/efficiency`, p as any),
  playtime: (id: number, p?: Filters) => get<any>(`/players/${id}/playtime`, p as any),
  fouls: (id: number, p?: Filters) => get<any>(`/players/${id}/fouls`, p as any),
  gamelog: (id: number, p?: Filters) => get<any>(`/players/${id}/gamelog`, p as any),
  gameDetail: (id: number, gameId: string) => get<any>(`/players/${id}/games/${gameId}`),
  trends: (id: number, p?: Filters) => get<any>(`/players/${id}/trends`, p as any),
  career: (id: number) => get<any>(`/players/${id}/career`),
  impact: (id: number, p?: Filters) => get<any>(`/players/${id}/impact`, p as any),
  compare: (a: number, b: number, p?: Filters) => get<any>("/compare", { a, b, ...p }),
  games: (p?: Record<string, unknown>) => get<any[]>("/games", p),
  investigate: (gameId: string) => get<any>(`/games/${gameId}/investigate`),
  leaders: (p?: Record<string, unknown>) => get<any[]>("/league/leaders", p),
  similar: (id: number, p?: Record<string, unknown>) => get<any>(`/league/similar/${id}`, p),
  ask: (body: { question: string; mode?: string; context?: Record<string, unknown> }) =>
    fetch(`${BASE}/ai/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(async (r) => {
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        throw new Error(b.detail || `AI request failed (${r.status})`);
      }
      return r.json();
    }),
};
