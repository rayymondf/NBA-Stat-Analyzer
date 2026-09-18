import { lazy, Suspense, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import SearchPalette from "./components/SearchPalette";
import { useSearchPalette } from "./hooks/useSearchPalette";

const Home = lazy(() => import("./pages/Home"));
const PlayerProfile = lazy(() => import("./pages/PlayerProfile"));
const GameDetailPage = lazy(() => import("./pages/GameDetail"));
const GamesPage = lazy(() => import("./pages/Games"));
const ComparePage = lazy(() => import("./pages/Compare"));
const ModelLab = lazy(() => import("./pages/ModelLab"));
const AiMode = lazy(() => import("./pages/AiMode"));

function ThemeToggle() {
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme ?? "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="w-8 h-8 rounded-lg border border-edge text-ink-muted hover:text-ink transition-colors"
      title="Toggle theme"
    >
      {theme === "dark" ? "☀" : "🌙"}
    </button>
  );
}

const navLink = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 text-[13px] rounded-lg font-medium transition-colors ${
    isActive
      ? "text-ink bg-surface-2"
      : "text-ink-muted hover:text-ink hover:bg-surface"
  }`;

function DataFreshnessFooter() {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  if (!meta) return null;
  return (
    <footer className="max-w-6xl mx-auto px-4 py-6 mt-8 border-t border-edge text-[11px] text-ink-muted flex flex-wrap gap-x-4 gap-y-1">
      <span>
        Data: official NBA.com stats covering every game from the{" "}
        <strong className="text-ink-2">{meta.seasons[meta.seasons.length - 1]}</strong> season through{" "}
        <strong className="text-ink-2">{meta.current_season}</strong>
        {meta.data_through && (
          <>, up to the most recent game on <strong className="text-ink-2">{meta.data_through}</strong></>
        )}
        .
      </span>
      <span>
        The current season ({meta.current_season}) refreshes every 12 hours while games are being
        played; the nine seasons before it are complete and will never change. Each October the app
        rolls forward to the new NBA season.
      </span>
      <span>{meta.player_lookup_note}</span>
    </footer>
  );
}

export default function App() {
  const { open, setOpen } = useSearchPalette();
  const [staleData, setStaleData] = useState(false);
  useEffect(() => {
    const update = (event: Event) => {
      setStaleData((event as CustomEvent<string>).detail === "stale");
    };
    window.addEventListener("nba-cache-status", update);
    return () => window.removeEventListener("nba-cache-status", update);
  }, []);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-edge bg-page/85 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 min-h-14 py-2 flex flex-wrap sm:flex-nowrap items-center gap-2 sm:gap-3">
          <NavLink to="/" className="flex items-center gap-2 mr-2 shrink-0">
            <span
              className="w-6 h-6 rounded-md grid place-items-center text-[13px] font-bold text-white shrink-0"
              style={{ background: "var(--series-1)" }}
              aria-hidden="true"
            >
              N
            </span>
            <span className="hidden sm:block font-display font-semibold text-lg tracking-tight">
              NBA Stat Analyzer
            </span>
          </NavLink>
          <nav
            aria-label="Primary"
            className="order-last sm:order-none w-full sm:w-auto flex items-center gap-1 self-stretch overflow-x-auto"
          >
            <NavLink to="/" className={navLink} end>Players</NavLink>
            <NavLink to="/games" className={navLink}>Games</NavLink>
            <NavLink to="/model" className={navLink}>The Model</NavLink>
            <NavLink to="/ai" className={navLink}>
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--series-7)" }} />
                AI Mode
              </span>
            </NavLink>
          </nav>
          <div className="flex-1" />
          <button
            onClick={() => setOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-edge text-sm text-ink-muted hover:text-ink hover:border-ink-muted transition-colors"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
              <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span className="hidden md:block">Search players</span>
            <kbd className="hidden md:block text-[10px] border border-edge rounded px-1 py-0.5">Ctrl K</kbd>
          </button>
          <ThemeToggle />
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {staleData && (
          <div role="status" className="mb-4 rounded-lg border border-[var(--series-4)] bg-surface px-4 py-2 text-xs text-ink-2 flex items-center gap-3">
            <span className="flex-1">NBA.com is temporarily unavailable. Some results are from the bounded stale cache and may not include the latest games.</span>
            <button className="underline underline-offset-2" onClick={() => setStaleData(false)}>Dismiss</button>
          </div>
        )}
        <Suspense fallback={<div className="text-sm text-ink-muted py-8">Loading…</div>}>
          <Routes>
            <Route path="/" element={<Home onSearch={() => setOpen(true)} />} />
            <Route path="/player/:id" element={<PlayerProfile />} />
            <Route path="/player/:id/game/:gameId" element={<GameDetailPage />} />
            <Route path="/games" element={<GamesPage />} />
            <Route path="/model" element={<ModelLab />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/ai" element={<AiMode />} />
          </Routes>
        </Suspense>
      </main>

      <DataFreshnessFooter />

      <SearchPalette open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
