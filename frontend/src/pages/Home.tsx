import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { num } from "../lib/format";
import { AnimatedNumber, ErrorState, Skeleton } from "../components/ui";
import PlayerAvatar from "../components/PlayerAvatar";

export default function Home({ onSearch }: { onSearch: () => void }) {
  const { data: leaders, isLoading, error, refetch } = useQuery({
    queryKey: ["leaders-home"], queryFn: () => api.leaders({ stat: "PTS", limit: 8 }),
  });
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  return (
    <div className="space-y-7 sm:space-y-9">
      <section className="discovery-header section-in">
        <div className="eyebrow mb-3">Your view of the game</div>
        <h1 className="font-display text-3xl sm:text-5xl font-extrabold tracking-tight leading-[1.12]">Every player.<br className="sm:hidden" /> A clearer picture.</h1>
        <p className="text-sm sm:text-base text-ink-2 mt-3 max-w-xl leading-relaxed">Explore performance, compare players, and see the story behind their shots.</p>
        <button type="button" onClick={onSearch} className="discovery-search mt-5" aria-label="Find an NBA player">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></svg>
          <span className="flex-1 text-left">Find an NBA player</span><span aria-hidden="true">→</span>
        </button>
        <p className="text-xs text-ink-muted mt-2">Search current players. Explore their available past seasons.</p>
      </section>
      <section aria-labelledby="leaders-title">
        <div className="flex flex-wrap justify-between items-end gap-2 mb-4">
          <div><div className="eyebrow mb-1">League leaders{meta && ` · ${meta.current_season}`}</div><h2 id="leaders-title" className="font-display text-xl sm:text-2xl font-bold tracking-tight">Leading the scoring.</h2></div>
          <span className="text-xs text-ink-muted">Points per game</span>
        </div>
        {error && <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />}
        <div className="grid md:grid-cols-2 gap-x-6 lg:gap-x-10">
          {isLoading && Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-[76px] mb-1 rounded-xl" />)}
          {leaders?.map((leader, index) => <Link key={leader.player_id} to={`/player/${leader.player_id}`} className="leader-row group">
            <span className="w-6 text-sm tnum text-ink-muted shrink-0">{String(index + 1).padStart(2, "0")}</span>
            <PlayerAvatar playerId={leader.player_id} name={leader.name} className="w-12 h-12" />
            <div className="min-w-0 flex-1"><div className="text-sm font-semibold truncate group-hover:text-accent transition-colors">{leader.name}</div><div className="text-xs text-ink-muted mt-0.5">{leader.team}</div></div>
            <div className="text-xl font-display font-bold tnum shrink-0"><AnimatedNumber value={leader.value} format={num} /></div>
            <span className="text-ink-muted ml-1" aria-hidden="true">↗</span>
          </Link>)}
        </div>
        {!isLoading && !error && leaders?.length === 0 && <p className="card p-5 text-sm text-ink-muted">Season leaders are not available yet. Search for a player to explore past seasons.</p>}
      </section>
      <section aria-label="Explore the analysis" className="grid sm:grid-cols-3 gap-4">
        {[
          { to: "/compare", number: "01", title: "Compare players", text: "Two players. One view. Put their performance side by side.", color: "var(--primary)" },
          { to: "/model", number: "02", title: "Understand shot quality", text: "Explore actual shooting alongside the model’s estimate for those shots.", color: "var(--secondary)" },
          { to: "/games", number: "03", title: "Break down a game", text: "Follow the runs, key performances, and numbers behind the result.", color: "var(--tertiary)" },
        ].map(item => <Link key={item.to} to={item.to} className="card-tonal card-hover p-5 sm:p-6 group">
          <div className="flex justify-between items-center text-xs mb-6"><span className="tnum font-bold text-sm" style={{ color: item.color }}>{item.number}</span><span aria-hidden="true" style={{ color: item.color }} className="text-base transition-transform duration-200 group-hover:translate-x-0.5">↗</span></div>
          <h2 className="font-display font-bold text-lg tracking-tight">{item.title}</h2>
          <p className="text-sm text-ink-2 leading-relaxed mt-2">{item.text}</p>
        </Link>)}
      </section>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-edge pt-5 text-sm">
        <p className="text-ink-muted">Have a specific question about the numbers?</p><Link to="/ai" className="btn btn-tonal btn-sm">Ask AI <span aria-hidden="true">→</span></Link>
      </div>
    </div>
  );
}
