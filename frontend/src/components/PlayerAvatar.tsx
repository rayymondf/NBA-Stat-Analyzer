import { useState } from "react";

/** Local initials remain visible when the external image is blocked or unavailable. */
export default function PlayerAvatar({ playerId, name, className = "w-12 h-12" }: {
  playerId: number; name: string; className?: string;
}) {
  const [failedId, setFailedId] = useState<number | null>(null);
  const initials = name.split(/\s+/).filter(Boolean).map(part => part[0]).slice(0, 2).join("");
  return <span className={`relative inline-flex items-center justify-center overflow-hidden rounded-full bg-surface-2 shrink-0 ${className}`} aria-hidden="true">
    <span className="font-display font-bold text-ink-muted">{initials}</span>
    {failedId !== playerId && <img src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${playerId}.png`} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover bg-surface-2" onError={() => setFailedId(playerId)} />}
  </span>;
}
