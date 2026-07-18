export const pct = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "–" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "–" : v.toFixed(digits);

export const signed = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;

export const ordinal = (n: number) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
};

export const teamLogo = (teamId: number | string) =>
  `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`;
