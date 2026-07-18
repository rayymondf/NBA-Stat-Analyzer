import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { num, pct, teamLogo } from "../lib/format";
import { HowItsMade, Skeleton } from "../components/ui";
import FilterBar, { type ProfileFilters } from "../components/profile/FilterBar";
import OverviewSection from "../components/profile/OverviewSection";
import ShootingSection from "../components/profile/ShootingSection";
import EfficiencySection from "../components/profile/EfficiencySection";
import PlaytimeSection from "../components/profile/PlaytimeSection";
import FoulsSection from "../components/profile/FoulsSection";
import GameLogSection from "../components/profile/GameLogSection";
import TrendsSection from "../components/profile/TrendsSection";
import ImpactSection from "../components/profile/ImpactSection";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "shooting", label: "Shooting" },
  { id: "efficiency", label: "Efficiency" },
  { id: "playtime", label: "Playtime" },
  { id: "fouls", label: "Fouls" },
  { id: "gamelog", label: "Game Log" },
  { id: "trends", label: "Trends" },
  { id: "impact", label: "Impact" },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

const AI_CHIPS = (name: string, season?: string) => [
  { q: `How is ${name} playing lately?` },
  { q: `What are ${name}'s shooting strengths and weaknesses?` },
  { q: `Compare ${name}'s ${season ?? "current"} season to the previous one.` },
  { q: `Does ${name} beat the shot-quality model this season?` },
  { q: `Find players similar to ${name}.` },
];

export default function PlayerProfile() {
  const { id } = useParams();
  const playerId = Number(id);
  const navigate = useNavigate();
  const [section, setSection] = useState<SectionId>("overview");
  const [filters, setFilters] = useState<ProfileFilters>({ perMode: "per_game" });

  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const season = filters.season ?? meta?.current_season;
  const effFilters = { ...filters, season };

  const { data: summary, isLoading } = useQuery({
    queryKey: ["summary", playerId, season, filters.season_type],
    queryFn: () => api.summary(playerId, { season, season_type: filters.season_type }),
    enabled: !!season,
  });

  const pg = summary?.stats?.per_game ?? {};
  const sh = summary?.stats?.shooting ?? {};

  return (
    <div>
      {/* ---- Hero ---- */}
      <div className="card overflow-hidden mb-4">
        <div
          className="px-6 pt-6 pb-5"
          style={{
            background:
              "linear-gradient(135deg, color-mix(in oklab, var(--series-1) 22%, var(--surface)) 0%, var(--surface) 70%)",
          }}
        >
          {isLoading || !summary ? (
            <div className="flex gap-5 items-center">
              <Skeleton className="w-24 h-24 rounded-full" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-7 w-56" />
                <Skeleton className="h-4 w-72" />
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-5 items-center">
              <img
                src={summary.headshot}
                alt={summary.name}
                className="w-24 h-24 rounded-full object-cover bg-surface-2 border-2 border-edge"
                onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
              />
              <div className="flex-1 min-w-52">
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="font-display text-3xl font-semibold tracking-tight">{summary.name}</h1>
                  {summary.team_id && (
                    <img src={teamLogo(summary.team_id)} alt="" className="w-8 h-8" />
                  )}
                </div>
                <p className="text-sm text-ink-2 mt-1">
                  {summary.team_name ?? "Free agent"}
                  {summary.jersey && ` · #${summary.jersey}`}
                  {summary.position && ` · ${summary.position}`}
                </p>
                <p className="text-xs text-ink-muted mt-0.5">
                  {summary.age && `Age ${summary.age}`}
                  {summary.height && ` · ${summary.height}`}
                  {summary.weight && ` · ${summary.weight} lb`}
                  {summary.experience != null && ` · ${summary.experience} seasons`}
                </p>
              </div>
              <div className="flex gap-6 text-center">
                <Hero label="PPG" value={num(pg.PTS)} />
                <Hero label="RPG" value={num(pg.REB)} />
                <Hero label="APG" value={num(pg.AST)} />
                <Hero label="TS%" value={pct(sh.TS_PCT)} />
                <Hero label="FG%" value={pct(sh.FG_PCT)} />
                <Hero label="3P%" value={pct(sh.FG3_PCT)} />
              </div>
            </div>
          )}
          {summary?.blurb && (
            <p className="mt-4 text-sm text-ink-2 max-w-3xl leading-relaxed">{summary.blurb}</p>
          )}
          {summary && (
            <div className="mt-3 flex gap-2 flex-wrap">
              {AI_CHIPS(summary.name, season).map((c) => (
                <button
                  key={c.q}
                  onClick={() =>
                    navigate("/ai", {
                      state: { question: c.q, context: { player_id: playerId, season } },
                    })
                  }
                  className="text-[11px] px-2.5 py-1 rounded-full border border-edge text-ink-2 hover:text-ink hover:border-ink-muted transition-colors"
                >
                  <span style={{ color: "var(--series-7)" }}>✦</span> {c.q}
                </button>
              ))}
              <button
                onClick={() => navigate(`/model?mode=h2h&a=${playerId}`)}
                className="text-[11px] px-2.5 py-1 rounded-full border border-edge text-ink-2 hover:text-ink hover:border-ink-muted transition-colors"
              >
                ⇄ Compare with another player
              </button>
            </div>
          )}
        </div>

        {/* ---- Section tabs ---- */}
        <div className="px-3 border-t border-edge flex overflow-x-auto">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={`px-3.5 py-2.5 text-sm whitespace-nowrap border-b-2 transition-colors ${
                section === s.id
                  ? "border-[var(--series-1)] text-ink font-medium"
                  : "border-transparent text-ink-muted hover:text-ink-2"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* ---- Filters ---- */}
      <div className="mb-4">
        <FilterBar filters={effFilters} onChange={setFilters} />
        {["shooting", "efficiency", "playtime", "fouls", "trends", "impact"].includes(section) && (
          <p className="text-[11px] text-ink-muted mt-1.5">
            This section follows the season and season-type filters; game-level splits apply to Overview and Game Log.
          </p>
        )}
      </div>

      {/* ---- Active section ---- */}
      {season && (
        <>
          {section === "overview" && <OverviewSection playerId={playerId} filters={effFilters} />}
          {section === "shooting" && <ShootingSection playerId={playerId} filters={effFilters} />}
          {section === "efficiency" && <EfficiencySection playerId={playerId} filters={effFilters} />}
          {section === "playtime" && <PlaytimeSection playerId={playerId} filters={effFilters} />}
          {section === "fouls" && <FoulsSection playerId={playerId} filters={effFilters} />}
          {section === "gamelog" && <GameLogSection playerId={playerId} filters={effFilters} />}
          {section === "trends" && <TrendsSection playerId={playerId} filters={effFilters} />}
          {section === "impact" && <ImpactSection playerId={playerId} filters={effFilters} />}
        </>
      )}
      <HowItsMade>
        Player data comes live from NBA.com's official stats through the free
        nba_api library and is cached in a local SQLite database on this PC.
        Every number, percentile and chart on these tabs is computed server
        side with pandas from real game logs, shot charts and play-by-play.
        Nothing here is estimated by AI; the one machine-learning number, the
        shot-quality card in the Shooting tab, is clearly labeled as a model
        estimate.
      </HowItsMade>
    </div>
  );
}

function Hero({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xl font-bold tnum">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-ink-muted">{label}</div>
    </div>
  );
}
