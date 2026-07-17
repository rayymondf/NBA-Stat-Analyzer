import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { num } from "../lib/format";
import { Skeleton } from "../components/ui";

const AI_EXAMPLES = [
  "Is Jayson Tatum inefficient in elimination games?",
  "Compare Steph Curry and Damian Lillard as three-point shooters",
  "Who is scoring efficiently with low playing time?",
  "Why did the Knicks lose their last game?",
];

export default function Home({ onSearch }: { onSearch: () => void }) {
  const navigate = useNavigate();
  const { data: leaders, isLoading } = useQuery({
    queryKey: ["leaders-home"],
    queryFn: () => api.leaders({ stat: "PTS", limit: 8 }),
  });
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });

  return (
    <div className="py-8">
      <section className="text-center max-w-2xl mx-auto pt-10 pb-14">
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
          Explore NBA stats.
          <br />
          <span style={{ color: "var(--series-1)" }}>Investigate what they mean.</span>
        </h1>
        <p className="mt-4 text-ink-2 text-base">
          Interactive shot charts, efficiency dashboards and trends for season participants
          and current roster players — plus an AI analyst that answers questions with real,
          calculated evidence.
        </p>
        {meta && (
          <div className="mt-2 text-xs text-ink-muted space-y-1">
            <p>
              Live official NBA data · {meta.current_season} season
              {meta.data_through && ` · updated through ${meta.data_through}`}
            </p>
            <p>{meta.player_lookup_note}</p>
          </div>
        )}
        <button
          onClick={onSearch}
          className="mt-8 w-full max-w-md mx-auto flex items-center gap-3 px-5 py-3.5 rounded-xl border border-edge bg-surface text-ink-muted hover:border-ink-muted transition-colors text-sm"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          Search {meta?.current_season ?? "current"} and current roster players…
          <kbd className="ml-auto text-[10px] border border-edge rounded px-1.5 py-0.5">Ctrl K</kbd>
        </button>
      </section>

      <section className="mb-12">
        <h2 className="text-sm font-semibold text-ink-2 uppercase tracking-wider mb-4">
          Scoring leaders
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {isLoading &&
            Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          {leaders?.map((l) => (
            <Link
              key={l.player_id}
              to={`/player/${l.player_id}`}
              className="card p-3 flex items-center gap-3 hover:border-ink-muted transition-colors"
            >
              <img
                src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${l.player_id}.png`}
                alt=""
                loading="lazy"
                className="w-12 h-12 rounded-full object-cover bg-surface-2"
              />
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{l.name}</div>
                <div className="text-xs text-ink-muted">{l.team}</div>
                <div className="text-xs tnum mt-0.5">
                  <span className="font-semibold">{num(l.value)}</span>
                  <span className="text-ink-muted"> pts/g</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-ink-2 uppercase tracking-wider mb-4">
          Ask AI Mode
        </h2>
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
    </div>
  );
}
