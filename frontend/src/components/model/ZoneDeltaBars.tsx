import { pct } from "../../lib/format";

/** Per-zone actual vs expected, as diverging bars plus a refined table. */
export default function ZoneDeltaBars({ zones }: {
  zones: { zone: string; shots: number; expected_fg: number; actual_fg: number; delta: number }[];
}) {
  if (!zones?.length) return null;
  const maxAbs = Math.max(...zones.map((z) => Math.abs(z.delta)), 0.02);
  return (
    <div>
      <div className="space-y-1.5 mb-4">
        {zones.map((z) => {
          const w = (Math.abs(z.delta) / maxAbs) * 50;
          const up = z.delta >= 0;
          return (
            <div key={z.zone} className="grid grid-cols-[130px_1fr_56px] items-center gap-2 text-xs">
              <span className="text-ink-2 truncate">{z.zone}</span>
              <div className="relative h-2.5">
                <div className="absolute inset-y-0 left-1/2 w-px bg-baseline" />
                <div
                  className="bar-fill absolute inset-y-0 rounded-full"
                  style={{
                    left: up ? "50%" : `${50 - w}%`,
                    width: `${w}%`,
                    background: up ? "var(--delta-up)" : "var(--delta-down)",
                  }}
                />
              </div>
              <span
                className="tnum font-medium text-right"
                style={{ color: up ? "var(--delta-up)" : "var(--delta-down)" }}
              >
                {z.delta > 0 ? "+" : ""}{(z.delta * 100).toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-ink-muted">
            <th className="text-left font-medium pb-1.5">Zone</th>
            <th className="text-right font-medium pb-1.5">Shots</th>
            <th className="text-right font-medium pb-1.5">Expected FG</th>
            <th className="text-right font-medium pb-1.5">Actual FG</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-edge">
          {zones.map((z) => (
            <tr key={z.zone}>
              <td className="py-1.5 text-ink-2">{z.zone}</td>
              <td className="py-1.5 text-right tnum">{z.shots}</td>
              <td className="py-1.5 text-right tnum text-ink-2">{pct(z.expected_fg)}</td>
              <td className="py-1.5 text-right tnum font-medium">{pct(z.actual_fg)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
