import { useEffect, useRef, useState, type ReactNode } from "react";
import { GLOSSARY } from "../lib/glossary";
import { ordinal } from "../lib/format";

/** Editorial page header: kicker, serif headline, muted dek, hairline rule. */
export function PageHeader({ kicker, title, dek }: {
  kicker?: string; title: ReactNode; dek?: ReactNode;
}) {
  return (
    <div className="mb-8 section-in">
      {kicker && <div className="eyebrow mb-2">{kicker}</div>}
      <h1 className="font-display text-3xl sm:text-4xl font-semibold tracking-tight leading-tight">
        {title}
      </h1>
      {dek && <p className="text-sm text-ink-2 mt-2 max-w-2xl leading-relaxed">{dek}</p>}
      <div className="rule mt-6" />
    </div>
  );
}

/** Count-up number; respects prefers-reduced-motion. */
export function AnimatedNumber({ value, format }: {
  value: number; format?: (n: number) => string;
}) {
  const fmt = format ?? ((n: number) => `${Math.round(n)}`);
  const [shown, setShown] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const dur = 500;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(value * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value]);
  return <span className="tnum">{fmt(shown)}</span>;
}

/** Collapsible "how this section is made" strip. */
export function HowItsMade({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rule mt-10 pt-3">
      <button
        onClick={() => setOpen(!open)}
        className="eyebrow flex items-center gap-1.5 hover:text-ink-2 transition-colors"
      >
        <span
          className="inline-block transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        >
          ›
        </span>
        How this is made
      </button>
      {open && (
        <p className="text-xs text-ink-2 leading-relaxed mt-2 max-w-2xl section-in">
          {children}
        </p>
      )}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card p-5 ${className}`}>{children}</div>;
}

export function CardTitle({ children, tip }: { children: ReactNode; tip?: string }) {
  return (
    <h3 className="text-sm font-semibold text-ink-2 uppercase tracking-wider mb-4 flex items-center gap-1.5">
      {children}
      {tip && <GlossaryTip term={tip} />}
    </h3>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function SkeletonCard({ lines = 4 }: { lines?: number }) {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="skeleton h-3.5" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="card p-6 text-center">
      <p className="text-ink-2 text-sm">Couldn't load this section.</p>
      <p className="text-ink-muted text-xs mt-1">{message}</p>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="card p-6 text-center text-ink-muted text-sm">{message}</div>
  );
}

/** Hover tooltip that explains a stat in plain English. */
export function GlossaryTip({ term, label }: { term: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const text = GLOSSARY[term];
  if (!text) return label ? <span>{label}</span> : null;
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {label && <span>{label}</span>}
      <button
        aria-label={`What is ${term}?`}
        className="ml-0.5 w-3.5 h-3.5 rounded-full border border-edge text-[9px] leading-none text-ink-muted hover:text-ink hover:border-ink-muted transition-colors cursor-help"
        tabIndex={0}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        ?
      </button>
      {open && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-60 p-2.5 rounded-lg text-xs leading-relaxed normal-case font-normal tracking-normal text-ink bg-surface-2 border border-edge shadow-xl">
          {text}
        </span>
      )}
    </span>
  );
}

/** Animated horizontal percentile bar: "better than N% of <position>". */
export function PercentileBar({
  label, value, percentile, poolLabel, format,
}: {
  label: string;
  value: string;
  percentile: number;
  poolLabel?: string;
  format?: string;
}) {
  const color =
    percentile >= 80 ? "var(--series-1)" :
    percentile >= 55 ? "var(--series-5)" :
    percentile >= 30 ? "var(--series-4)" : "var(--series-8)";
  return (
    <div className="flex items-center gap-3 py-1" title={poolLabel}>
      <div className="w-28 shrink-0 text-xs text-ink-2 flex items-center">
        <GlossaryTip term={format ?? label} label={label} />
      </div>
      <div className="w-14 shrink-0 text-sm tnum font-medium text-right">{value}</div>
      <div className="flex-1 h-2 rounded-full bg-surface-2 overflow-hidden">
        <div
          className="bar-fill h-full rounded-full"
          style={{ width: `${percentile}%`, background: color }}
        />
      </div>
      <div className="w-12 shrink-0 text-xs tnum text-ink-muted text-right">
        {ordinal(percentile)}
      </div>
    </div>
  );
}

export function StatTile({ label, value, sub, tip }: {
  label: string; value: ReactNode; sub?: string; tip?: string;
}) {
  return (
    <div className="card px-4 py-3 min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-ink-muted flex items-center gap-1">
        {label}
        {tip && <GlossaryTip term={tip} />}
      </div>
      <div className="text-xl font-semibold tnum mt-0.5">{value}</div>
      {sub && <div className="text-[11px] text-ink-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange }: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg bg-surface-2 p-0.5 border border-edge">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1 text-xs rounded-md transition-colors ${
            value === o.value
              ? "bg-surface text-ink shadow-sm font-medium"
              : "text-ink-muted hover:text-ink-2"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
