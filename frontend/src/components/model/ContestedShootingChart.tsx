import { pct } from "../../lib/format";
import type { ContestedBucket, ContestedRating } from "../../lib/types";

/**
 * FG% by closest-defender distance, tightest -> most open, as horizontal
 * analytical bars with the attempt frequency alongside. Descriptive NBA
 * tracking splits of how this player shoots when guarded closely vs open;
 * not a defensive rating and not an input to the xFG model.
 */
export default function ContestedShootingChart({ buckets, rating }: {
  buckets: ContestedBucket[];
  rating: ContestedRating;
}) {
  if (!buckets?.length) return null;
  const maxFg = Math.max(...buckets.map((b) => b.fg_pct), 0.5);
  return (
    <div>
      <div className="space-y-1.5 mb-4">
        {buckets.map((b) => {
          const w = (b.fg_pct / maxFg) * 100;
          return (
            <div key={b.range} className="grid grid-cols-[120px_1fr_48px_56px] items-center gap-2 text-xs">
              <span className="text-ink-2 truncate" title={b.label}>{b.range}</span>
              <div className="relative h-2.5 bg-surface-2 rounded-full overflow-hidden">
                <div
                  className="bar-fill absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${w}%`, background: "var(--series-4)" }}
                />
              </div>
              <span className="tnum font-medium text-right">{pct(b.fg_pct)}</span>
              <span className="tnum text-ink-muted text-right">{pct(b.frequency)}</span>
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-[120px_1fr_48px_56px] gap-2 text-[10px] uppercase tracking-wider text-ink-muted mb-4">
        <span>Defender</span><span /><span className="text-right">FG%</span><span className="text-right">Freq</span>
      </div>

      <div className="border-t border-edge pt-3">
        <div className="flex items-baseline justify-between flex-wrap gap-x-4 gap-y-1">
          <span className="text-xs text-ink-muted">Offensive shot-making under tight coverage</span>
          <span className="text-sm font-semibold capitalize">{rating.label}</span>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs mt-2">
          <span>Tight (&lt;4 ft): <strong className="tnum">{rating.tight_fg_pct != null ? pct(rating.tight_fg_pct) : "—"}</strong> on {rating.tight_fga} FGA</span>
          <span>Open (4+ ft): <strong className="tnum">{rating.open_fg_pct != null ? pct(rating.open_fg_pct) : "—"}</strong> on {rating.open_fga} FGA</span>
          {rating.contest_drop != null && (
            <span>Open − tight: <strong className="tnum">{rating.contest_drop > 0 ? "+" : ""}{(rating.contest_drop * 100).toFixed(1)} pp</strong></span>
          )}
        </div>
        {rating.confidence === "low" && (
          <p className="text-xs mt-2" style={{ color: "var(--critical)" }}>Low confidence — small sample.</p>
        )}
        <p className="text-xs text-ink-muted leading-relaxed mt-2">{rating.caveat}</p>
      </div>
    </div>
  );
}
