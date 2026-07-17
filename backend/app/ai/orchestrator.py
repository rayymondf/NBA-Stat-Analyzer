"""Gemini-powered NBA research assistant.

The model orchestrates which tools to call; every number in the final report
comes from tool outputs (the app's own computed statistics). The final answer
is a structured JSON report the frontend renders with evidence, counterevidence,
data scope and entity links.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

from ..nba.seasons import current_season
from . import tools

VERDICTS = ["Supported", "Mostly supported", "Mixed", "Misleading",
            "Not supported", "Insufficient evidence"]

SYSTEM_PROMPT = f"""You are the research assistant inside "NBA Stat Analyzer".
You answer NBA questions using ONLY numbers returned by your tools — never from
memory. The current NBA season is {{season}} (today: {{today}}).

Rules:
- Resolve player names to IDs with search_player before other tools.
- NEVER state a statistic you did not get from a tool this conversation.
- Actively look for counterevidence before concluding; report it honestly.
- Small samples: always mention sample sizes; below ~10 games, say the
  evidence is weak. If the data is unavailable or insufficient, say so
  plainly instead of guessing.
- EARLY IN A SEASON: if the current season has fewer than ~15 games for the
  subject (or a tool result includes a "note" about a small sample), ALSO call
  the same tool for the previous season (use get_previous_season to get its
  string), then base your answer mainly on the fuller season and clearly label
  which season each number comes from. Never present a 3-5 game current-season
  sample as if it settles the question.
- Comparisons: name who is better per category — never declare someone
  universally better unless the evidence is lopsided across the board.
- Claim verification: first restate the claim as a measurable definition,
  then gather evidence, a baseline (league or position context), and
  counterexamples, then give a verdict from: {", ".join(VERDICTS)}.
- Keep the tone of a sharp, neutral basketball analyst. Explain advanced
  stats briefly when used (e.g. "TS% — shooting efficiency incl. 3s and FTs").

After investigating, reply with ONLY a JSON object (no markdown fences):
{{{{
  "answer_markdown": "your full answer in markdown (2-6 short paragraphs or bullets)",
  "verdict": "one of the verdict strings above, or null if not a claim check",
  "key_findings": [{{{{"claim": "short statement", "evidence": "the exact numbers backing it"}}}}],
  "counterevidence": ["honest caveats or opposing data points, [] if none"],
  "data_scope": {{{{
    "seasons": ["seasons analyzed"],
    "sample": "games/players analyzed, e.g. '60 games (2025-26 regular season)'",
    "definitions": ["stat definitions used"],
    "filters": "filters applied, or 'none'"
  }}}},
  "links": [{{{{"type": "player" | "game", "id": "player_id or game_id", "label": "display name"}}}}],
  "confidence": "high" | "medium" | "low"
}}}}
Include a links entry for every player and game you analyzed."""


class AiUnavailable(Exception):
    pass


class AiRateLimited(Exception):
    pass


def _client():
    from google import genai
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key == "your-key-here":
        raise AiUnavailable(
            "No Gemini API key configured. Add GEMINI_API_KEY to backend/.env "
            "(free key: https://aistudio.google.com → Get API key).")
    return genai.Client(api_key=key)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"answer_markdown": text, "verdict": None, "key_findings": [],
            "counterevidence": [], "data_scope": {}, "links": [],
            "confidence": "low"}


def _tool_trace(response) -> list[dict]:
    """Executed tool calls + results from the SDK's automatic-calling history."""
    trace = []
    history = getattr(response, "automatic_function_calling_history", None) or []
    for content in history:
        for part in getattr(content, "parts", None) or []:
            fc = getattr(part, "function_call", None)
            if fc is not None:
                trace.append({"tool": fc.name, "args": dict(fc.args or {})})
            fr = getattr(part, "function_response", None)
            if fr is not None and trace:
                for t in reversed(trace):
                    if t["tool"] == fr.name and "result" not in t:
                        result = fr.response
                        t["result"] = result.get("result", result) if isinstance(result, dict) else result
                        break
    return trace


def ask(question: str, mode: str = "auto",
        context: dict | None = None) -> dict:
    from google.genai import errors, types

    client = _client()
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

    prompt_parts = [f"Investigation type: {mode}." if mode != "auto" else "",
                    f"Question: {question}"]
    if context:
        prompt_parts.append(
            "Context from the page the user came from (use these IDs directly): "
            + json.dumps(context))
    prompt = "\n".join(p for p in prompt_parts if p)

    system = SYSTEM_PROMPT.format(season=current_season(),
                                  today=datetime.now().strftime("%Y-%m-%d"))

    # Primary model first, then lite fallbacks. Verified 2026-07: new free-tier
    # accounts only have quota on current-generation models — older ones
    # (gemini-2.x) return 404 "retired" or 429 "limit: 0", so they must NOT be
    # in this list. The flash models 503 under global demand spikes; the lite
    # models are the reliable fallback.
    candidates = [model, "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]

    def _attempt(candidate: str):
        return client.models.generate_content(
            model=candidate,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=tools.ALL_TOOLS,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=6),
                temperature=0.2,
            ),
        )

    response = None
    last_err: Exception | None = None
    for candidate in dict.fromkeys(candidates):
        try:
            response = _attempt(candidate)
            model = candidate
            break
        except errors.ClientError as err:
            if getattr(err, "code", None) == 429 or "429" in str(err):
                last_err = err
                # Per-minute limit with a short reset? Wait it out once, then
                # retry the same model before falling back.
                m = re.search(r"retry in ([\d.]+)s", str(err))
                if m and float(m.group(1)) <= 35 and "limit: 0" not in str(err):
                    time.sleep(float(m.group(1)) + 1)
                    try:
                        response = _attempt(candidate)
                        model = candidate
                        break
                    except (errors.ClientError, errors.ServerError) as err2:
                        last_err = err2
                continue  # next model — each has its own quota
            if getattr(err, "code", None) in (401, 403) or "API key" in str(err):
                raise AiUnavailable(
                    "The Gemini API key was rejected. Create a free key at "
                    "https://aistudio.google.com → 'Get API key' and put it in "
                    "backend/.env as GEMINI_API_KEY.") from err
            if getattr(err, "code", None) == 404:  # model retired → try next
                last_err = err
                continue
            raise
        except errors.ServerError as err:  # 5xx: overloaded → try next model
            last_err = err
            continue

    if response is None:
        err_text = str(last_err)
        if "PerDay" in err_text:
            raise AiRateLimited(
                "Today's free Gemini allowance is used up. It resets around "
                "midnight Pacific time — AI Mode will work again tomorrow. "
                "All other app features keep working.")
        if getattr(last_err, "code", None) == 429 or "429" in err_text:
            raise AiRateLimited(
                "The free Gemini tier is rate-limited right now — wait about "
                "a minute and ask again.")
        raise AiRateLimited(
            "Google's AI servers are overloaded right now (temporary, their "
            "side). Wait a minute and ask again — the app automatically tries "
            "backup models.")

    report = _extract_json(response.text or "")
    report.setdefault("key_findings", [])
    report.setdefault("counterevidence", [])
    report.setdefault("data_scope", {})
    report.setdefault("links", [])
    report["tool_trace"] = _tool_trace(response)
    report["model"] = model
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    return report
