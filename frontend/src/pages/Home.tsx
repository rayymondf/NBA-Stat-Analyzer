import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { num } from "../lib/format";
import { AnimatedNumber, HowItsMade, Skeleton } from "../components/ui";

const AI_EXAMPLES = [
  "Who are the top five scorers in the NBA this season?",
  "How has Stephen Curry been playing in his last 10 games?",
  "Compare Shai Gilgeous-Alexander and Luka Doncic this season",
  "What are Victor Wembanyama's stats this season?",
];

export default function Home({ onSearch }: { onSearch: () => void }) {
  const navigate = useNavigate();
  const { data: leaders, isLoading } = useQuery({
    queryKey: ["leaders-home"],
    queryFn: () => api.leaders({ stat: "PTS", limit: 8 }),
  });
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });

  return (
    <div className="py-6">
      {/* ---- Cover ---- */}
      <section className="max-w-3xl mx-auto text-center pt-10 pb-12 section-in">
        <div className="eyebrow mb-3">The season, quantified</div>
        <h1 className="font-display text-5xl sm:text-6xl font-semibold tracking-tight leading-[1.05]">
          <span className="block sm:whitespace-nowrap">Explore NBA stats.</span>
          <span className="block sm:whitespace-nowrap" style={{ color: "var(--series-1)" }}>
            Investigate what they mean.
          </span>
        </h1>
        <p className="mt-5 text-ink-2 text-base max-w-2xl mx-auto leading-relaxed">
          Shot charts, dashboards and trends for every player in the league —
          <br className="hidden sm:block" /> plus a model trained on real NBA shots and an
          AI analyst that proves every answer with the numbers.
        </p>
        {meta && (
          <p className="mt-3 text-xs text-ink-muted tracking-wide uppercase">
            Official NBA.com stats · seasons {meta.seasons[meta.seasons.length - 1]} to{" "}
            {meta.current_season}
            {meta.data_through && ` · latest game: ${meta.data_through}`}
          </p>
        )}
        <button
          onClick={onSearch}
          className="mt-8 w-full max-w-md mx-auto flex items-center gap-3 px-5 py-3.5 rounded-lg border border-edge bg-surface text-ink-muted hover:border-ink-muted transition-colors text-sm"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          Search any current NBA player
          <kbd className="ml-auto text-[10px] border border-edge rounded px-1.5 py-0.5">Ctrl K</kbd>
        </button>
        {meta && (
          <p className="mt-2 text-xs text-ink-muted max-w-md mx-auto">
            {meta.player_lookup_note}
          </p>
        )}
      </section>

      <div className="rule mb-10" />

      {/* ---- Leaderboard ---- */}
      <section className="mb-12">
        <div className="eyebrow mb-4">The leaderboard · points per game</div>
        <div className="grid sm:grid-cols-2 gap-x-10">
          {isLoading &&
            Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-md mb-1" />
            ))}
          {leaders?.map((l, i) => (
            <Link
              key={l.player_id}
              to={`/player/${l.player_id}`}
              className="flex items-center gap-4 py-2.5 border-b border-edge hover:bg-surface transition-colors px-2 -mx-2 group"
            >
              <span className="font-display text-xl text-ink-muted w-6 text-right shrink-0">
                {i + 1}
              </span>
              <img
                src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${l.player_id}.png`}
                alt=""
                loading="lazy"
                className="w-11 h-11 rounded-full object-cover bg-surface-2 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium truncate group-hover:underline underline-offset-2">
                  {l.name}
                </div>
                <div className="text-xs text-ink-muted">{l.team}</div>
              </div>
              <div className="text-lg font-semibold shrink-0">
                <AnimatedNumber value={l.value} format={(n) => num(n)} />
                <span className="text-[10px] text-ink-muted font-normal ml-1">PPG</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* ---- The Model teaser ---- */}
      <section className="mb-12">
        <Link
          to="/model"
          className="card p-6 flex flex-wrap items-center gap-5 hover:border-ink-muted transition-colors group block"
        >
          <div className="flex-1 min-w-64">
            <div className="eyebrow mb-1.5">Machine learning</div>
            <div className="font-display text-2xl font-semibold group-hover:underline underline-offset-4">
              Player vs the Model
            </div>
            <p className="text-sm text-ink-2 mt-1.5 leading-relaxed">
              Pick any player and see whether they beat a machine trained on
              hundreds of thousands of real NBA shots. Who makes more than
              their shots deserve?
            </p>
          </div>
          <span className="text-2xl text-ink-muted group-hover:text-ink transition-colors">→</span>
        </Link>
      </section>

      {/* ---- Ask the analyst ---- */}
      <section>
        <div className="eyebrow mb-4">Ask the analyst</div>
        <div className="grid sm:grid-cols-2 gap-3">
          {AI_EXAMPLES.map((q) => (
            <button
              key={q}
              onClick={() => navigate("/ai", { state: { question: q } })}
              className="card p-4 text-left text-sm text-ink-2 hover:border-ink-muted hover:text-ink transition-colors"
            >
              <span className="mr-2" style={{ color: "var(--series-7)" }}>✦</span>
              {q}
            </button>
          ))}
        </div>
      </section>

      <HowItsMade>
        Player data comes live from NBA.com's official stats through the free
        nba_api library and is cached in a local SQLite database on this PC.
        Every number, percentile and chart is computed server side with pandas.
        Nothing on this page is estimated by AI.
      </HowItsMade>
    </div>
  );
}
