import type {
  AiReport, Career, Comparison, Efficiency, Fouls, GameDetail, GameLog,
  Impact, Investigation, Leader, ListedGame, ModelInfo, Overview, Playtime,
  PlayerSummary, ProblemDetails, ShotProfile, ShotQuality, SimilarPlayers,
  Trends,
} from "./types";

const BASE = "/api/v1";

export const DATASET_URL = `${BASE}/ml/dataset.csv`;

export class ApiError extends Error {
  readonly status: number;
  readonly requestId?: string;
  readonly retryable: boolean;

  constructor(
    message: string,
    status: number,
    requestId?: string,
    retryable = false,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
    this.retryable = retryable;
  }
}

async function responseJson<T>(res: Response): Promise<T> {
  const cacheStatus = res.headers.get("X-Data-Cache");
  if (cacheStatus && cacheStatus !== "none" && typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("nba-cache-status", { detail: cacheStatus }));
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({} as Partial<ProblemDetails>)) as Partial<ProblemDetails>;
    throw new ApiError(
      body.detail || `Request failed (${res.status})`,
      res.status,
      body.request_id ?? res.headers.get("X-Request-ID") ?? undefined,
      body.retryable ?? false,
    );
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string, params?: object, init?: RequestInit): Promise<T> {
  const entries = params
    ? Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null && value !== "")
      .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    : [];
  const qs = entries.length ? `?${entries.join("&")}` : "";
  const url = `${BASE}${path}${qs}`;
  const res = init ? await fetch(url, init) : await fetch(url);
  return responseJson<T>(res);
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

export type { Percentile, ShotPoint, Zone } from "./types";

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
  search: (q: string, signal?: AbortSignal) => get<SearchResult[]>(
    "/players/search", { q }, signal ? { signal } : undefined,
  ),
  summary: (id: number, p?: Filters) => get<PlayerSummary>(`/players/${id}/summary`, p),
  overview: (id: number, p?: Filters) => get<Overview>(`/players/${id}/overview`, p),
  shooting: (id: number, p?: Record<string, unknown>) => get<ShotProfile>(`/players/${id}/shooting`, p),
  shotQuality: (id: number, p?: Filters) => get<ShotQuality>(`/players/${id}/shot-quality`, p),
  efficiency: (id: number, p?: Filters) => get<Efficiency>(`/players/${id}/efficiency`, p),
  playtime: (id: number, p?: Filters) => get<Playtime>(`/players/${id}/playtime`, p),
  fouls: (id: number, p?: Filters) => get<Fouls>(`/players/${id}/fouls`, p),
  gamelog: (id: number, p?: Filters) => get<GameLog>(`/players/${id}/gamelog`, p),
  gameDetail: (id: number, gameId: string) => get<GameDetail>(`/players/${id}/games/${gameId}`),
  trends: (id: number, p?: Filters) => get<Trends>(`/players/${id}/trends`, p),
  career: (id: number) => get<Career>(`/players/${id}/career`),
  impact: (id: number, p?: Filters) => get<Impact>(`/players/${id}/impact`, p),
  compare: (a: number, b: number, p?: Filters) => get<Comparison>("/compare", { a, b, ...p }),
  modelInfo: () => get<ModelInfo>("/ml/model-info"),
  games: (p?: Record<string, unknown>) => get<ListedGame[]>("/games", p),
  investigate: (gameId: string) => get<Investigation>(`/games/${gameId}/investigate`),
  leaders: (p?: Record<string, unknown>) => get<Leader[]>("/league/leaders", p),
  similar: (id: number, p?: Record<string, unknown>) => get<SimilarPlayers>(`/league/similar/${id}`, p),
  ask: (body: { question: string; mode?: string; context?: Record<string, unknown> }) =>
    fetch(`${BASE}/ai/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((response) => responseJson<AiReport>(response)),
};
