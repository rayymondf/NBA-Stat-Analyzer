import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Card, Segmented } from "../components/ui";

type Mode = "auto" | "player" | "claim" | "compare" | "game";

interface Report {
  answer_markdown: string;
  verdict: string | null;
  key_findings: { claim: string; evidence: string }[];
  counterevidence: string[];
  data_scope: { seasons?: string[]; sample?: string; definitions?: string[]; filters?: string };
  links: { type: string; id: string | number; label: string }[];
  confidence?: string;
  tool_trace?: { tool: string; args: Record<string, unknown> }[];
  generated_at?: string;
  model?: string;
  cached?: boolean;
  model_attempts?: number;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    thinking_tokens?: number;
    tool_prompt_tokens?: number;
    cached_input_tokens?: number;
    total_tokens?: number;
  };
}

interface Turn {
  question: string;
  report?: Report;
  error?: string;
}

const VERDICT_COLORS: Record<string, string> = {
  Supported: "var(--good)",
  "Mostly supported": "var(--series-5)",
  Mixed: "var(--warning)",
  Misleading: "var(--serious)",
  "Not supported": "var(--critical)",
  "Insufficient evidence": "var(--ink-muted)",
};

const PROGRESS_STEPS = [
  "Interpreting the question…",
  "Deciding what evidence is needed…",
  "Pulling real stats from NBA data…",
  "Checking for counterexamples…",
  "Writing the report…",
];

/** Tiny markdown renderer (bold, headers, bullets, paragraphs). */
function Markdown({ text }: { text: string }) {
  const html = text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^### (.+)$/gm, "<h4 class='font-semibold mt-3 mb-1'>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3 class='font-semibold mt-3 mb-1'>$1</h3>")
    .replace(/^[-*] (.+)$/gm, "<li class='ml-4 list-disc'>$1</li>")
    .replace(/\n\n/g, "</p><p class='mt-2'>");
  return (
    <div
      className="text-sm leading-relaxed text-ink [&_strong]:text-ink"
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  );
}

function Progress() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PROGRESS_STEPS.length - 1)), 3500);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="flex items-center gap-3 text-sm text-ink-2 py-3">
      <span className="w-4 h-4 rounded-full border-2 border-edge border-t-[var(--series-7)] animate-spin" />
      {PROGRESS_STEPS[step]}
    </div>
  );
}

function ReportCard({ r }: { r: Report }) {
  const [showScope, setShowScope] = useState(false);
  return (
    <Card className="space-y-4">
      {r.verdict && (
        <span
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold text-white"
          style={{ background: VERDICT_COLORS[r.verdict] ?? "var(--ink-muted)" }}
        >
          Verdict: {r.verdict}
        </span>
      )}
      <Markdown text={r.answer_markdown} />

      {r.key_findings?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-2">Evidence</h4>
          <div className="space-y-1.5">
            {r.key_findings.map((f, i) => (
              <div key={i} className="flex gap-2.5 text-xs border border-edge rounded-lg p-2.5">
                <span className="shrink-0 mt-0.5" style={{ color: "var(--good)" }}>✓</span>
                <div>
                  <div className="text-ink font-medium">{f.claim}</div>
                  <div className="text-ink-muted tnum mt-0.5">{f.evidence}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {r.counterevidence?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-2">Counterevidence & caveats</h4>
          <div className="space-y-1">
            {r.counterevidence.map((c, i) => (
              <div key={i} className="flex gap-2 text-xs text-ink-2">
                <span style={{ color: "var(--serious)" }}>⚠</span> {c}
              </div>
            ))}
          </div>
        </div>
      )}

      {r.links?.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {r.links.map((l, i) =>
            l.type === "player" ? (
              <Link key={i} to={`/player/${l.id}`}
                className="text-xs px-2.5 py-1 rounded-full border border-edge hover:border-ink-muted transition-colors"
                style={{ color: "var(--series-1)" }}>
                {l.label} →
              </Link>
            ) : (
              <Link key={i} to={`/games?game=${l.id}`}
                className="text-xs px-2.5 py-1 rounded-full border border-edge hover:border-ink-muted transition-colors"
                style={{ color: "var(--series-6)" }}>
                {l.label} →
              </Link>
            ),
          )}
        </div>
      )}

      <div className="border-t border-edge pt-2">
        <button onClick={() => setShowScope(!showScope)}
          className="text-[11px] text-ink-muted hover:text-ink">
          {showScope ? "▾" : "▸"} Data scope, definitions & tool calls
          {r.confidence && ` · confidence: ${r.confidence}`}
        </button>
        {showScope && (
          <div className="mt-2 text-[11px] text-ink-muted space-y-1.5">
            {r.data_scope?.seasons && <div>Seasons: {r.data_scope.seasons.join(", ")}</div>}
            {r.data_scope?.sample && <div>Sample: {r.data_scope.sample}</div>}
            {r.data_scope?.filters && <div>Filters: {r.data_scope.filters}</div>}
            {r.data_scope?.definitions?.map((d, i) => <div key={i}>• {d}</div>)}
            {r.tool_trace && r.tool_trace.length > 0 && (
              <div className="pt-1">
                Analyses run:{" "}
                {r.tool_trace.map((t) => t.tool).join(" → ")}
              </div>
            )}
            {r.cached && <div>Reused a cached answer · no Gemini quota used</div>}
            {r.usage?.total_tokens != null && (
              <div>
                {r.cached ? "Original answer usage" : "Gemini usage"}: {r.usage.total_tokens.toLocaleString()} tokens
                {r.usage.thinking_tokens != null && ` · ${r.usage.thinking_tokens.toLocaleString()} thinking`}
                {r.model_attempts != null && ` · ${r.model_attempts} model attempt${r.model_attempts === 1 ? "" : "s"}`}
              </div>
            )}
            {r.generated_at && <div>Generated {new Date(r.generated_at).toLocaleString()} · {r.model}</div>}
          </div>
        )}
      </div>
    </Card>
  );
}

export default function AiMode() {
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("auto");
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const context = useRef<Record<string, unknown> | undefined>(undefined);
  const autoSubmitted = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: (q: string) => api.ask({ question: q, mode, context: context.current as any }),
    onSuccess: (report, q) =>
      setTurns((t) => t.map((turn) => (turn.question === q && !turn.report && !turn.error ? { ...turn, report } : turn))),
    onError: (err, q) =>
      setTurns((t) => t.map((turn) => (turn.question === q && !turn.report && !turn.error ? { ...turn, error: (err as Error).message } : turn))),
  });

  const submit = (q: string) => {
    const question = q.trim();
    if (!question || mutation.isPending) return;
    setTurns((t) => [...t, { question }]);
    setInput("");
    mutation.mutate(question);
  };

  // Prefilled question coming from a player page / game page
  useEffect(() => {
    const state = location.state as { question?: string; context?: Record<string, unknown> } | null;
    if (state?.question && !autoSubmitted.current) {
      autoSubmitted.current = true;
      context.current = state.context;
      submit(state.question);
      window.history.replaceState({}, "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, mutation.isPending]);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <span style={{ color: "var(--series-7)" }}>✦</span> AI Mode
          </h1>
          <p className="text-xs text-ink-muted mt-0.5">
            Answers are built from this app's computed stats — every claim shows its evidence.
          </p>
        </div>
        <Segmented
          options={[
            { value: "auto" as Mode, label: "Auto" },
            { value: "player" as Mode, label: "Player" },
            { value: "claim" as Mode, label: "Claim check" },
            { value: "compare" as Mode, label: "Compare" },
            { value: "game" as Mode, label: "Game" },
          ]}
          value={mode}
          onChange={setMode}
        />
      </div>

      <div className="space-y-4 mb-4">
        {turns.length === 0 && (
          <Card className="text-sm text-ink-muted">
            Ask anything about NBA players, games or claims — e.g. <em>"Is Jayson Tatum
            inefficient in elimination games?"</em>, <em>"Compare Curry and Lillard as
            three-point shooters"</em>, or open a game from the Games tab and ask why a team lost.
            <br /><br />
            The first question can take 20–60 seconds while data is fetched and analyzed.
          </Card>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[85%] px-4 py-2.5 rounded-2xl rounded-br-md text-sm"
                style={{ background: "color-mix(in oklab, var(--series-7) 22%, var(--surface))" }}>
                {t.question}
              </div>
            </div>
            {t.report && <ReportCard r={t.report} />}
            {t.error && (
              <Card className="text-sm" >
                <span style={{ color: "var(--serious)" }}>⚠</span> {t.error}
              </Card>
            )}
            {!t.report && !t.error && <Progress />}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); submit(input); }}
        className="sticky bottom-4 card p-2 flex gap-2 shadow-xl"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a player, a claim, a comparison or a game…"
          className="flex-1 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-ink-muted"
        />
        <button
          type="submit"
          disabled={mutation.isPending || !input.trim()}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-40 transition-opacity"
          style={{ background: "var(--series-7)" }}
        >
          Ask
        </button>
      </form>
    </div>
  );
}
