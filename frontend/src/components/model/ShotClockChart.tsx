import { pct } from "../../lib/format";
import type { ContestedShotClockBucket } from "../../lib/types";

/**
 * FG% by shot-clock range, from early in the clock to the final seconds, as
 * horizontal analytical bars with attempt frequency alongside. Descriptive NBA
 * tracking splits of how this player shoots early vs late in the clock; not an
 * input to the xFG model.
 */
export default function ShotClockChart({ buckets }: { buckets: ContestedShotClockBucket[] }) {
  if (!buckets?.length) return null;
  const maxFg = Math.max(...buckets.map((b) => b.fg_pct), 0.5);
  return (
    <div>
      <div className="space-y-1.5 mb-2">
        {buckets.map((b) => {
          const w = (b.fg_pct / maxFg) * 100;
          return (
            <div key={b.range} className="grid grid-cols-[120px_1fr_48px_56px] items-center gap-2 text-xs">
              <span className="text-ink-2 truncate" title={b.range}>{b.range}</span>
              <div className="relative h-2.5 bg-surface-2 rounded-full overflow-hidden">
                <div
                  className="bar-fill absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${w}%`, background: "var(--series-6)" }}
                />
              </div>
              <span className="tnum font-medium text-right">{pct(b.fg_pct)}</span>
              <span className="tnum text-ink-muted text-right">{pct(b.frequency)}</span>
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-[120px_1fr_48px_56px] gap-2 text-[10px] uppercase tracking-wider text-ink-muted">
        <span>Shot clock</span><span /><span className="text-right">FG%</span><span className="text-right">Freq</span>
      </div>
    </div>
  );
}
