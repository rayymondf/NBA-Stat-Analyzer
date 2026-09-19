import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { useSearchPalette } from "./hooks/useSearchPalette";
import SearchPalette from "./components/SearchPalette";
import ErrorBoundary from "./components/ErrorBoundary";
import Home from "./pages/Home";

const PlayerProfile = lazy(() => import("./pages/PlayerProfile"));
const GameDetailPage = lazy(() => import("./pages/GameDetail"));
const GamesPage = lazy(() => import("./pages/Games"));
const ComparePage = lazy(() => import("./pages/Compare"));
const ModelLab = lazy(() => import("./pages/ModelLab"));
const AiMode = lazy(() => import("./pages/AiMode"));
const destinations = [
  { to: "/", label: "Players" },
  { to: "/games", label: "Games" },
  { to: "/compare", label: "Compare" },
  { to: "/model", label: "Shot Quality" },
  { to: "/ai", label: "Ask AI" },
];
const navLink = ({ isActive }: { isActive: boolean }) =>
  `nav-link ${isActive ? "nav-link-active" : ""}`;

function ThemeToggle() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? "dark");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("nba-theme", theme); } catch { /* storage may be disabled */ }
  }, [theme]);
  return (
    <button type="button" className="icon-button" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
      {theme === "dark" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
          <circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
          <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" />
        </svg>
      )}
    </button>
  );
}

function DataFreshnessFooter() {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  return (
    <footer className="app-width mt-12 border-t border-edge py-6 text-xs text-ink-muted">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <span>NBA Stat Analyzer <span aria-hidden="true">·</span> Independent basketball analytics</span>
        {meta && <details className="max-w-lg">
          <summary className="cursor-pointer text-ink-2">NBA.com data{meta.data_through ? ` · through ${meta.data_through}` : ""}</summary>
          <p className="mt-3 leading-relaxed">Seasons {meta.seasons.at(-1)}–{meta.current_season}. Recent data is cached and may lag official updates. Historical statistics can be revised by the source.</p>
          <p className="mt-2 leading-relaxed">{meta.player_lookup_note}</p>
        </details>}
      </div>
    </footer>
  );
}

export default function App() {
  const { open, setOpen } = useSearchPalette();
  const [staleData, setStaleData] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const menuDialog = useRef<HTMLDialogElement>(null);
  const location = useLocation();
  useEffect(() => {
    const update = (event: Event) => {
      // A fresh response for another section must not erase a stale warning.
      if ((event as CustomEvent<string>).detail === "stale") setStaleData(true);
    };
    window.addEventListener("nba-cache-status", update);
    return () => window.removeEventListener("nba-cache-status", update);
  }, []);
  useEffect(() => { setMenuOpen(false); }, [location.pathname, location.search]);
  useEffect(() => {
    const dialog = menuDialog.current;
    if (menuOpen) dialog?.showModal();
    else if (dialog?.open) { dialog.close(); menuButton.current?.focus(); }
  }, [menuOpen]);

  const search = () => { setMenuOpen(false); setOpen(true); };
  return (
    <div className="min-h-screen flex flex-col">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <header className="sticky top-0 z-40 border-b border-edge bg-page/95 backdrop-blur-xl">
        <div className="app-width flex h-[72px] items-center gap-3">
          <NavLink to="/" className="flex items-center gap-2.5 shrink-0 mr-3">
            <span className="brand-mark" aria-hidden="true">N<span className="text-white/65">.</span></span>
            <span className="hidden sm:block font-display font-extrabold text-lg tracking-tight">NBA<span className="text-ink-muted font-semibold"> / Stats</span></span>
            <span className="sr-only sm:hidden">NBA / Stats home</span>
          </NavLink>
          <nav aria-label="Primary" className="hidden lg:flex items-center gap-1">
            {destinations.map(({ to, label }) => <NavLink key={to} to={to} end={to === "/"} className={navLink}>{label}</NavLink>)}
          </nav>
          <div className="flex-1" />
          <button type="button" onClick={search} className="search-trigger">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" />
            </svg>
            <span className="sr-only md:not-sr-only">Search players</span><kbd className="hidden xl:block text-[10px] rounded border border-edge px-1.5" aria-hidden="true">Ctrl K</kbd>
          </button>
          <ThemeToggle />
          <button type="button" ref={menuButton} onClick={() => setMenuOpen(true)} className="icon-button lg:hidden" aria-label="Open navigation" aria-haspopup="dialog" aria-expanded={menuOpen}>
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
          </button>
        </div>
      </header>
      <dialog ref={menuDialog} className="navigation-drawer" aria-labelledby="navigation-title" onCancel={() => setMenuOpen(false)} onClose={() => setMenuOpen(false)}>
        <div className="flex justify-between items-center mb-6">
          <h2 id="navigation-title" className="font-display text-xl font-bold">Explore NBA stats</h2>
          <button type="button" className="icon-button" aria-label="Close navigation" onClick={() => setMenuOpen(false)}>✕</button>
        </div>
        <nav aria-label="Mobile primary" className="flex flex-col gap-2">
          {destinations.map(({ to, label }) => <NavLink key={to} to={to} end={to === "/"} className={navLink} onClick={() => setMenuOpen(false)}>{label}</NavLink>)}
        </nav>
        <button type="button" onClick={search} className="button-primary w-full mt-6">Search players</button>
      </dialog>
      <main id="main-content" tabIndex={-1} className="app-width flex-1 py-6 sm:py-8 min-w-0 w-full">
        {staleData && <div role="status" className="mb-5 rounded-xl border border-warning/40 bg-surface px-4 py-3 text-sm text-ink-2 flex items-start gap-3">
          <span className="flex-1">Some results use previously saved data while NBA.com is unavailable. They may not include the latest games.</span>
          <button type="button" className="underline underline-offset-2 shrink-0" onClick={() => setStaleData(false)}>Dismiss</button>
        </div>}
        <ErrorBoundary key={location.pathname}>
          <Suspense fallback={<div role="status" className="card p-8 text-sm text-ink-muted">Loading analysis…</div>}>
            <Routes>
              <Route path="/" element={<Home onSearch={search} />} />
              <Route path="/player/:id" element={<PlayerProfile />} />
              <Route path="/player/:id/game/:gameId" element={<GameDetailPage />} />
              <Route path="/games" element={<GamesPage />} />
              <Route path="/model" element={<ModelLab />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/ai" element={<AiMode />} />
              <Route path="*" element={<div className="card p-8"><h1 className="font-display text-2xl font-bold">Page not found</h1><NavLink to="/" className="button-primary inline-flex mt-5">Explore players</NavLink></div>} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
      <DataFreshnessFooter />
      <SearchPalette open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
