import { lazy, Suspense, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { num, pct, teamLogo } from "../lib/format";
import { Button, ErrorState, HowItsMade, Skeleton } from "../components/ui";
import FilterBar, { type PerMode, type ProfileFilters } from "../components/profile/FilterBar";
import OverviewSection from "../components/profile/OverviewSection";

const ShootingSection = lazy(() => import("../components/profile/ShootingSection"));
const EfficiencySection = lazy(() => import("../components/profile/EfficiencySection"));
const PlaytimeSection = lazy(() => import("../components/profile/PlaytimeSection"));
const FoulsSection = lazy(() => import("../components/profile/FoulsSection"));
const GameLogSection = lazy(() => import("../components/profile/GameLogSection"));
const TrendsSection = lazy(() => import("../components/profile/TrendsSection"));
const ImpactSection = lazy(() => import("../components/profile/ImpactSection"));

const PRIMARY = [{ id: "overview", label: "Overview" }, { id: "shooting", label: "Shooting" }, { id: "gamelog", label: "Games" }] as const;
const MORE = [{ id: "efficiency", label: "Efficiency" }, { id: "playtime", label: "Playtime" }, { id: "fouls", label: "Fouls" }, { id: "trends", label: "Trends" }, { id: "impact", label: "Impact" }] as const;
const SECTIONS = [...PRIMARY, ...MORE] as const;
type SectionId = (typeof SECTIONS)[number]["id"];
const PER_MODES: PerMode[] = ["per_game", "per_36", "per_75", "per_100"];
const TEAMS = ["ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS"];

function pick<T extends string | number>(value: string | null, allowed: readonly T[], fallback: T): T { return allowed.includes(value as T) ? value as T : fallback; }
function date(value: string | null) { return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : undefined; }

export default function PlayerProfile() {
  const { id } = useParams(); const playerId = Number(id); const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const section = pick<SectionId>(params.get("tab"), SECTIONS.map((item) => item.id), "overview");
  const requestedSeason = params.get("season");
  const season = meta?.seasons.includes(requestedSeason ?? "") ? requestedSeason! : undefined;
  const seasonType = pick(params.get("season_type"), ["Regular Season", "Playoffs"], "Regular Season");
  const filters = useMemo<ProfileFilters>(() => ({
    season, season_type: seasonType, perMode: pick(params.get("per_mode"), PER_MODES, "per_game"),
    location: pick(params.get("location"), ["home", "away"], "") || undefined,
    outcome: pick(params.get("outcome"), ["W", "L"], "") || undefined,
    starter: params.get("starter") === "true" ? true : params.get("starter") === "false" ? false : undefined,
    last_n: pick(params.get("last_n"), [5, 10, 20], 0) || undefined,
    opponent: pick(params.get("opponent"), TEAMS, "") || undefined,
    date_from: date(params.get("date_from")), date_to: date(params.get("date_to")),
  }), [params, season, seasonType]);
  const update = (patch: Record<string, string | number | boolean | null | undefined>) => {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([key, value]) => value === undefined || value === null || value === "" || value === false ? next.delete(key) : next.set(key, String(value)));
    setParams(next);
  };
  const setFilters = (next: ProfileFilters) => update({
    season: next.season, season_type: next.season_type === "Regular Season" ? undefined : next.season_type,
    per_mode: next.perMode === "per_game" ? undefined : next.perMode, location: next.location, outcome: next.outcome,
    starter: next.starter, last_n: next.last_n, opponent: next.opponent, date_from: next.date_from, date_to: next.date_to,
  });
  const { data: summary, isLoading, error, refetch } = useQuery({
    queryKey: ["summary", playerId, filters.season, filters.season_type],
    queryFn: () => api.summary(playerId, { season: filters.season, season_type: filters.season_type }), enabled: Number.isInteger(playerId) && playerId > 0,
  });
  const effectiveSeason = filters.season ?? summary?.season ?? meta?.current_season;
  const effectiveFilters = { ...filters, season: effectiveSeason };
  const pg = summary?.stats?.per_game ?? {}; const sh = summary?.stats?.shooting ?? {};
  const splitSection = section === "overview" || section === "gamelog";
  const chartQuarter = pick(params.get("quarter"), [1, 2, 3, 4, 5], 0) || null;
  const chartResult = pick(params.get("result"), ["all", "made", "missed"], "all");
  if (!Number.isInteger(playerId) || playerId < 1) return <ErrorState message="This player profile is unavailable." />;
  if (error && !summary) return <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />;

  return <div className="space-y-6">
    <section className="card overflow-hidden">
      <div className="px-4 py-5 sm:px-6" style={{ background: "linear-gradient(135deg, color-mix(in oklab, var(--primary) 16%, var(--surface)) 0%, var(--surface) 72%)" }}>
        {isLoading || !summary ? <ProfileSkeleton /> : <>
          <div className="flex flex-wrap items-center gap-4">
            <img src={summary.headshot} alt={summary.name ?? "NBA player"} className="h-16 w-16 rounded-full border-2 border-edge bg-surface-2 object-cover sm:h-20 sm:w-20" onError={(event) => { (event.target as HTMLImageElement).style.display = "none"; }} />
            <div className="min-w-44 flex-1"><div className="flex flex-wrap items-center gap-2"><h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">{summary.name}</h1>{summary.team_id && <img src={teamLogo(summary.team_id)} alt="" className="h-6 w-6" />}</div><p className="mt-1 text-sm text-ink-2">{summary.team_name ?? "Free agent"}{summary.jersey && ` · #${summary.jersey}`}{summary.position && ` · ${summary.position}`}</p><p className="text-xs text-ink-muted">{summary.age && `Age ${summary.age}`}{summary.height && ` · ${summary.height}`}{summary.experience != null && ` · ${summary.experience} seasons`}</p></div>
            <div className="grid grid-cols-2 gap-x-5 gap-y-2 text-center sm:flex sm:gap-x-6"><Hero label="PPG" value={num(pg.PTS)} /><Hero label="RPG" value={num(pg.REB)} /><Hero label="APG" value={num(pg.AST)} /><Hero label="TS%" value={pct(sh.TS_PCT)} /></div>
          </div>
          {summary.blurb && <p className="mt-3 max-w-3xl text-sm leading-relaxed text-ink-2">{summary.blurb}</p>}
          <div className="mt-4 flex flex-wrap gap-2"><Button variant="outlined" size="sm" onClick={() => navigate(`/compare?a=${playerId}&season=${encodeURIComponent(effectiveSeason ?? "")}&season_type=${encodeURIComponent(filters.season_type ?? "Regular Season")}`)}>Compare</Button><Button variant="tonal" size="sm" onClick={() => navigate("/ai", { state: { question: `How is ${summary.name ?? "this player"} playing lately?`, context: { player_id: playerId, season: effectiveSeason, season_type: filters.season_type } } })}><span style={{ color: "var(--tertiary)" }}>✦</span> Ask AI</Button></div>
        </>}
      </div>
      <div className="flex items-center gap-1 overflow-x-auto border-t border-edge px-2" aria-label="Player analysis sections">{PRIMARY.map((item) => <Tab key={item.id} item={item} active={section === item.id} onClick={() => update({ tab: item.id === "overview" ? undefined : item.id })} />)}<label className="ml-auto shrink-0 py-1.5"><span className="sr-only">More analysis</span><select aria-label="More analysis" value={MORE.some((item) => item.id === section) ? section : ""} onChange={(event) => update({ tab: event.target.value || undefined })} className="rounded-md bg-surface-container px-2 py-1.5 text-xs text-ink-muted outline-none hover:text-ink"><option value="">More analysis</option>{MORE.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>
    </section>
    <section className="card p-3 sm:p-4"><FilterBar filters={effectiveFilters} onChange={setFilters} showRate={section === "overview"} showSplits={splitSection} />{section === "overview" && <p className="mt-2 text-[11px] text-ink-muted">Percentiles use full-season, per-game numbers for position peers; game filters affect only the stat summary.</p>}{section === "shooting" && <p className="mt-2 text-[11px] text-ink-muted">Season and type set the shot profile. Quarter and make/miss controls apply only to the chart.</p>}</section>
    {effectiveSeason && <Suspense fallback={<Skeleton className="h-72 rounded-lg" />}>{section === "overview" && <OverviewSection playerId={playerId} filters={effectiveFilters} />}{section === "shooting" && <ShootingSection playerId={playerId} filters={effectiveFilters} chartFilters={{ quarter: chartQuarter, result: chartResult, onChange: (patch) => update({ quarter: patch.quarter, result: patch.result === "all" ? undefined : patch.result }) }} />}{section === "efficiency" && <EfficiencySection playerId={playerId} filters={effectiveFilters} />}{section === "playtime" && <PlaytimeSection playerId={playerId} filters={effectiveFilters} />}{section === "fouls" && <FoulsSection playerId={playerId} filters={effectiveFilters} />}{section === "gamelog" && <GameLogSection playerId={playerId} filters={effectiveFilters} />}{section === "trends" && <TrendsSection playerId={playerId} filters={effectiveFilters} />}{section === "impact" && <ImpactSection playerId={playerId} filters={effectiveFilters} />}</Suspense>}
    <HowItsMade>Player data comes live from NBA.com&apos;s official stats through the free nba_api library and is cached in a local SQLite database on this PC. Every number, percentile and chart on these tabs is computed server side with pandas from real game logs, shot charts and play-by-play. Nothing here is estimated by AI; the shot-quality card is clearly labeled as a model estimate.</HowItsMade>
  </div>;
}

function Tab({ item, active, onClick }: { item: (typeof PRIMARY)[number]; active: boolean; onClick: () => void }) { return <button onClick={onClick} className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors ${active ? "border-[var(--primary)] text-ink font-semibold" : "border-transparent text-ink-muted hover:text-ink-2"}`} aria-current={active ? "page" : undefined}>{item.label}</button>; }
function ProfileSkeleton() { return <div className="flex items-center gap-4"><Skeleton className="h-16 w-16 rounded-full" /><div className="flex-1 space-y-2"><Skeleton className="h-7 w-48" /><Skeleton className="h-4 w-64" /></div></div>; }
function Hero({ label, value }: { label: string; value: string }) { return <div><div className="text-lg font-bold tnum">{value}</div><div className="text-[10px] uppercase tracking-wider text-ink-muted">{label}</div></div>; }
