import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export default function SearchPalette({
  open, onClose, onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick?: (playerId: number, name: string) => void;
}) {
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const navigate = useNavigate();

  const { data: results = [], isFetching, error } = useQuery({
    queryKey: ["search", debouncedQ],
    queryFn: ({ signal }) => api.search(debouncedQ, signal),
    enabled: open && debouncedQ.length >= 2,
  });
  const visibleResults = q.trim() === debouncedQ ? results : [];

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQ(q.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [q]);

  useEffect(() => {
    if (open) {
      previousFocus.current = document.activeElement as HTMLElement | null;
      setQ("");
      setDebouncedQ("");
      setActive(0);
      window.setTimeout(() => inputRef.current?.focus(), 30);
    } else {
      previousFocus.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key === "Tab" && panelRef.current) {
        const focusable = Array.from(
          panelRef.current.querySelectorAll<HTMLElement>("input, button, [tabindex]:not([tabindex='-1'])"),
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => setActive(0), [visibleResults.length]);

  if (!open) return null;

  const pick = (id: number, name: string) => {
    onClose();
    if (onPick) onPick(id, name);
    else navigate(`/player/${id}`);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Search NBA players"
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh] bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        className="w-full max-w-xl card shadow-2xl overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-5 border-b border-edge">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="text-ink-muted shrink-0" aria-hidden="true">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(event) => setQ(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" && visibleResults.length) {
                event.preventDefault();
                setActive((value) => Math.min(value + 1, visibleResults.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((value) => Math.max(value - 1, 0));
              }
              const selected = visibleResults[active];
              if (event.key === "Enter" && selected) pick(selected.player_id, selected.name);
            }}
            placeholder="Search NBA players…"
            role="combobox"
            aria-label="Player name"
            aria-controls="player-search-results"
            aria-expanded={visibleResults.length > 0}
            aria-activedescendant={visibleResults[active] ? `player-option-${visibleResults[active].player_id}` : undefined}
            aria-busy={isFetching}
            className="flex-1 bg-transparent py-4 text-[15px] outline-none placeholder:text-ink-muted"
          />
          <kbd className="text-[10px] font-medium text-ink-muted border border-edge rounded-md px-2 py-1 shrink-0">ESC</kbd>
        </div>
        <div id="player-search-results" role="listbox" className="max-h-[22rem] overflow-y-auto p-2">
          {q.trim().length < 2 && (
            <p className="px-4 py-8 text-sm text-ink-muted text-center">Type at least two letters. Try “Wembanyama” or “Curry”.</p>
          )}
          {q.trim().length >= 2 && q.trim() !== debouncedQ && (
            <p className="px-4 py-8 text-sm text-ink-muted text-center">Waiting for you to finish typing…</p>
          )}
          {isFetching && <p className="px-4 py-8 text-sm text-ink-muted text-center">Searching…</p>}
          {error && <p role="alert" className="px-4 py-8 text-sm text-[var(--critical)] text-center">{(error as Error).message}</p>}
          {debouncedQ.length >= 2 && !isFetching && !error && visibleResults.length === 0 && (
            <p className="px-4 py-8 text-sm text-ink-muted text-center">No players found for “{debouncedQ}”.</p>
          )}
          {visibleResults.map((result, index) => (
            <button
              id={`player-option-${result.player_id}`}
              role="option"
              aria-selected={index === active}
              key={result.player_id}
              onMouseEnter={() => setActive(index)}
              onClick={() => pick(result.player_id, result.name)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors ${
                index === active ? "bg-surface-2" : ""
              }`}
            >
              <img
                src={result.headshot}
                alt=""
                loading="lazy"
                className="w-10 h-10 rounded-full object-cover bg-surface-2 shrink-0"
                onError={(event) => ((event.target as HTMLImageElement).style.visibility = "hidden")}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{result.name}</div>
                <div className="text-xs text-ink-muted">
                  {result.team ?? "Free agent"} · {result.position ?? "–"}{result.jersey ? ` · #${result.jersey}` : ""}
                </div>
                {!result.has_season_stats && (
                  <div className="text-[11px]" style={{ color: "var(--warning)" }}>
                    Current roster · no {result.lookup_season} appearances
                  </div>
                )}
              </div>
              {result.ppg != null && (
                <div className="text-xs tnum text-ink-muted shrink-0">
                  {result.ppg} pts · {result.rpg} reb · {result.apg} ast
                </div>
              )}
            </button>
          ))}
        </div>
        <div className="hidden sm:flex items-center gap-4 px-5 py-2.5 border-t border-edge text-[11px] text-ink-muted">
          <span className="flex items-center gap-1.5"><kbd className="border border-edge rounded px-1.5 py-0.5">↑</kbd><kbd className="border border-edge rounded px-1.5 py-0.5">↓</kbd> navigate</span>
          <span className="flex items-center gap-1.5"><kbd className="border border-edge rounded px-1.5 py-0.5">↵</kbd> open</span>
          <span className="flex items-center gap-1.5 ml-auto"><kbd className="border border-edge rounded px-1.5 py-0.5">esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
