import type { components } from "./schema.d.ts";

export type NullableNumber = number | null;
export type NumericMap = Record<string, NullableNumber>;
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  request_id: string;
  retryable: boolean;
}

export interface AggregateStats {
  games: number;
  wins?: number | null;
  losses?: number | null;
  starts?: number | null;
  totals?: NumericMap;
  per_game?: NumericMap;
  per_36?: NumericMap;
  per_75?: NumericMap;
  per_100?: NumericMap;
  shooting?: NumericMap;
  possessions?: number;
}

export interface Percentile {
  value: number;
  percentile: number;
  position_group: string;
  pool_size: number;
}

export type PercentileMap = Record<string, Percentile>;

export interface PlayerBio {
  player_id: number;
  name: string | null;
  team: string | null;
  team_id: number | null;
  team_name: string | null;
  position: string | null;
  jersey: string | null;
  height: string | null;
  weight: string | null;
  birthdate: string | null;
  country: string | null;
  experience: number | null;
  draft: { year: string | null; round: string | null; pick: string | null };
  from_year: string | null;
  to_year: string | null;
  headshot: string;
}

export interface PlayerSummary extends PlayerBio {
  age: number | null;
  season: string;
  season_type: string;
  stats: AggregateStats;
  percentiles: PercentileMap;
  blurb: string;
}

export interface Overview {
  filters: Record<string, string | number | boolean | null>;
  season_games: number;
  stats: AggregateStats;
  percentiles: PercentileMap;
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
  pct: NullableNumber;
  league_pct: NullableNumber;
  diff: NullableNumber;
  freq: number;
}

export interface DistanceBucket {
  range: string;
  fga: number;
  fgm: number;
  pct: number;
  freq: number;
}

export interface ShotProfile {
  points: ShotPoint[];
  zones: Zone[];
  by_distance: DistanceBucket[];
  totals: NumericMap;
  scoring_breakdown: NumericMap;
  season: string;
  season_type: string;
}

export interface ShotQualityZone {
  zone: string;
  shots: number;
  expected_fg: number;
  actual_fg: number;
  delta: number;
}

export interface ShotQualityUnavailable { available: false; reason: string }
export interface ShotQualityAvailable {
  available: true; season: string; season_type: string; shots: number;
  expected_efg: number; actual_efg: number; delta: number;
  raw_delta?: number; shrunk_delta?: number; confidence_interval_95?: [number, number];
  delta_per_100_shots: number; percentile: number | null;
  zones: ShotQualityZone[]; model: ModelIdentity; explanation: string;
  uncertainty_note?: string;
}
export type ShotQuality = ShotQualityAvailable | ShotQualityUnavailable;

export interface Efficiency {
  season: string;
  season_type: string;
  games: number;
  metrics: NumericMap;
  percentiles: PercentileMap;
}

export interface MinuteBucket {
  bucket: string;
  games: number;
  pts: number;
  reb: number;
  ast: number;
  ts_pct: NullableNumber;
}

export interface Playtime {
  season: string;
  season_type: string;
  games: number;
  team_games?: number | null;
  games_missed?: number | null;
  starts?: number | null;
  bench_games?: number | null;
  min_per_game?: number;
  min_total?: number;
  timeline?: Array<{ date: string; game_id: string; matchup: string; min: number; pts: number; pf: number; wl: string }>;
  by_minutes?: MinuteBucket[];
  foul_impact?: { games_5plus_fouls: number; avg_min_foul_trouble: NullableNumber; avg_min_normal: NullableNumber };
  q4?: { min_total: NullableNumber; min_per_game: NullableNumber; pts_total: NullableNumber; fg_pct: NullableNumber } | null;
  clutch?: {
    games: number; min_total: NullableNumber; min_per_game: NullableNumber;
    pts_total: NullableNumber; pts_per_game: NullableNumber; fg_pct: NullableNumber;
    plus_minus: NullableNumber; record: string;
  } | null;
}

export interface FoulSeriesPoint { date: string; pf: number; min: number }
export interface Fouls {
  season: string;
  season_type: string;
  games: number;
  pf_per_game?: number;
  pf_per_36?: NullableNumber;
  pf_total?: number;
  fouls_drawn_per_game?: NullableNumber;
  games_5_fouls?: number;
  games_6_fouls?: number;
  foul_trouble_rate?: number;
  avg_min_foul_trouble?: NullableNumber;
  avg_min_normal?: NullableNumber;
  series?: FoulSeriesPoint[];
  foul_types_recent?: { counts: Record<string, number>; opponent_fta_from_shooting_fouls_estimate: number; games_analyzed: number };
  note?: string;
}

export interface GameLogRow {
  game_id: string; date: string; matchup: string; opponent: string; home: boolean;
  wl: string; started: boolean | null; min: number; pts: number; reb: number;
  ast: number; stl: number; blk: number; tov: number; pf: number; fgm: number;
  fga: number; fg3m: number; fg3a: number; ftm: number; fta: number;
  plus_minus: NullableNumber; ts_pct: NullableNumber; usg_pct: NullableNumber;
}

export interface GameLog { filters: Overview["filters"]; rows: GameLogRow[] }

export interface TeamBlock { team_id: number; abbr: string; name: string; pts: number }
export interface PlayerLine extends GameLogRow { player_id: number; name: string; position: string; starter: boolean }
export interface TimelinePoint { t: number; period: number; clock: string; home: number; away: number; margin: number }
export interface ScoringEvent { period: number; clock: string; desc: string; home: string; away: string }
export interface GameDetail {
  game_id: string; season: string; season_type: string; home: TeamBlock; away: TeamBlock;
  player_line: PlayerLine | null; shots: ShotProfile; timeline: TimelinePoint[];
  scoring_events: ScoringEvent[];
}

export interface TrendPoint {
  date: string; game_id: string; pts: number; min: number; pts_roll: NullableNumber;
  ts_roll: NullableNumber; min_roll: NullableNumber; fga_roll: NullableNumber;
  fg3a_rate_roll: NullableNumber; usg_roll?: NullableNumber;
}
export interface Trends {
  season: string; season_type?: string; games: number; window?: number;
  series: TrendPoint[]; recent_form?: NumericMap;
}

export interface CareerRow {
  season: string; team: string; age: number; gp: number; gs: number; min: number;
  pts: number; reb: number; ast: number; stl: number; blk: number; tov: number;
  pf: number; fg_pct: number; fg3_pct: number; ft_pct: number; fga: number;
  fg3a: number; fta: number; ts_pct?: NullableNumber;
}
export interface Career { regular_season: CareerRow[]; playoffs: CareerRow[] }

export interface OnOffRow {
  season: string; on_court: NumericMap; off_court: NumericMap; net_diff: NullableNumber;
  off_diff: number; def_diff: number;
}
export interface Impact { season: string; season_type: string; current: OnOffRow | null; history: OnOffRow[]; disclaimer: string }

export interface ComparisonBlock {
  info: PlayerBio; stats: AggregateStats; percentiles: PercentileMap; zones: Zone[];
  shot_points: ShotPoint[]; efficiency: NumericMap;
}
export interface Comparison { season: string; season_type: string; a: ComparisonBlock; b: ComparisonBlock }

export interface ModelIdentity {
  trained_on_shots?: number; seasons?: string[]; brier?: number; auc?: number;
  trained_at?: string; model_version?: number; dataset_version?: string;
}

// Model-info types are derived directly from the OpenAPI contract
// (backend/app/schemas.py -> src/lib/schema.d.ts via `npm run generate:api`)
// so the frontend can never drift from the server's response shape.
export type ModelInfoAvailable = components["schemas"]["ModelInfoAvailable"];
export type ModelInfoUnavailable = components["schemas"]["ModelInfoUnavailable"];
export type CalibrationBucket = components["schemas"]["CalibrationPoint"];
// Kept aliases for existing consumers; now backed by the generated contract.
export type ModelAvailable = ModelInfoAvailable;
export type ModelUnavailable = ModelInfoUnavailable;
export type ModelInfo = ModelInfoAvailable | ModelInfoUnavailable;

// Shot-difficulty explainer (SHAP), derived from the OpenAPI contract.
export type ShotExplainer = components["schemas"]["ShotExplainerAvailable"];
export type ShotExplainerUnavailable = components["schemas"]["ShotExplainerUnavailable"];
export type ShotExplainerResponse = ShotExplainer | ShotExplainerUnavailable;
export type FeatureContribution = components["schemas"]["FeatureContribution"];

export interface ListedGameTeam { team_id: number; abbr: string; name: string; pts: number; wl: string }
export interface ListedGame { game_id: string; date: string; home: ListedGameTeam; away: ListedGameTeam }
export interface Evidence { label: string; value: string | number }
export interface Explanation { key: string; title: string; favored: string; score: number; summary: string; evidence_for: Evidence[]; evidence_against: Evidence[] }
export interface FourFactors { efg: number; tov: number; orb: number; ft: number }
export interface StarLine { player_id: number; name: string; team: string; pts: number; season_ppg: number; delta: number; ts_pct: NullableNumber; min: number }
export interface InvestigationTeam extends TeamBlock { home: boolean; winner: boolean }
export interface Investigation {
  game_id: string; season: string; season_type: string; teams: InvestigationTeam[];
  final: string; four_factors: Record<string, FourFactors>; explanations: Explanation[];
  star_lines: StarLine[]; runs: Array<Record<string, string | number>>;
  q4: Record<string, JsonValue> | null; method: string;
}

export interface Leader { player_id: number; name: string; team: string; gp: number; min: number; value: number; stat: string }
export interface SimilarPlayer { player_id: number; name: string; team: string; distance: number; profile: NumericMap }
export interface SimilarPlayers { target: { player_id: number; profile: NumericMap } | null; features?: string[]; matches: SimilarPlayer[]; method?: string }

export interface AiReport {
  answer_markdown: string; verdict: string | null;
  key_findings: Array<{ claim: string; evidence: string }>;
  counterevidence: string[];
  data_scope: { seasons?: string[]; sample?: string; definitions?: string[]; filters?: string };
  links: Array<{ type: string; id: string | number; label: string }>;
  confidence?: string;
  tool_trace?: Array<{ tool: string; args: Record<string, unknown>; result?: JsonValue }>;
  model?: string; generated_at?: string;
  usage?: Record<string, number>; model_attempts?: number; cached?: boolean;
}
