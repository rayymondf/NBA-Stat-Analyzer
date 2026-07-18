import { Navigate, useSearchParams } from "react-router-dom";

/** Old Compare URL: redirect into The Model's player-vs-player mode. */
export default function ComparePage() {
  const [params] = useSearchParams();
  const next = new URLSearchParams({ mode: "h2h" });
  const a = params.get("a");
  const b = params.get("b");
  if (a) next.set("a", a);
  if (b) next.set("b", b);
  return <Navigate to={`/model?${next.toString()}`} replace />;
}
