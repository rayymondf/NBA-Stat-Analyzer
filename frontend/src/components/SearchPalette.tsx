import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function useSearchPalette() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return { open, setOpen };
}

export default function SearchPalette({
  open, onClose, onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick?: (playerId: number, name: string) => void;
}) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const { data: results = [], isFetching } = useQuery({
    queryKey: ["search", q],
    queryFn: () => api.search(q),
    enabled: open && q.trim().length >= 2,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => setActive(0), [results.length]);

  if (!open) return null;

  const pick = (id: number, name: string) => {
    onClose();
    if (onPick) onPick(id, name);
    else navigate(`/player/${id}`);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[14vh] bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl card shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 border-b border-edge">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-ink-muted shrink-0">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, results.length - 1));
              if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
              if (e.key === "Enter" && results[active]) pick(results[active].player_id, results[active].name);
            }}
            placeholder="Search NBA players…"
            className="flex-1 bg-transparent py-3.5 text-sm outline-none placeholder:text-ink-muted"
          />
          <kbd className="text-[10px] text-ink-muted border border-edge rounded px-1.5 py-0.5">ESC</kbd>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {q.trim().length < 2 && (
            <p className="p-4 text-sm text-ink-muted">Type at least two letters — try "Wembanyama" or "Curry".</p>
          )}
          {q.trim().length >= 2 && !isFetching && results.length === 0 && (
            <p className="p-4 text-sm text-ink-muted">No players found for "{q}".</p>
          )}
          {results.map((r, i) => (
            <button
              key={r.player_id}
              onMouseEnter={() => setActive(i)}
              onClick={() => pick(r.player_id, r.name)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                i === active ? "bg-surface-2" : ""
              }`}
            >
              <img
                src={r.headshot}
                alt=""
                loading="lazy"
                className="w-9 h-9 rounded-full object-cover bg-surface-2"
                onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{r.name}</div>
                <div className="text-xs text-ink-muted">
                  {r.team ?? "Free agent"} · {r.position ?? "—"}{r.jersey ? ` · #${r.jersey}` : ""}
                </div>
              </div>
              {r.ppg != null && (
                <div className="text-xs tnum text-ink-muted shrink-0">
                  {r.ppg} pts · {r.rpg} reb · {r.apg} ast
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
