"""Gemini-powered NBA research assistant.

The model orchestrates which tools to call; every number in the final report
comes from tool outputs (the app's own computed statistics). The final answer
is a structured JSON report the frontend renders with evidence, counterevidence,
data scope and entity links.
"""
import hashlib
import json
import os
import re
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from ..nba import cache
from ..nba.seasons import current_season
from . import tools

VERDICTS = ["Supported", "Mostly supported", "Mixed", "Misleading",
            "Not supported", "Insufficient evidence"]
PROMPT_VERSION = "2026-07-18.1"
DEFAULT_CACHE_TTL_SECONDS = 12 * 3600
DEFAULT_MAX_OUTPUT_TOKENS = 1600
DEFAULT_MAX_REMOTE_CALLS = 6


class Finding(BaseModel):
    claim: str
    evidence: str


class DataScope(BaseModel):
    seasons: list[str]
    sample: str
    definitions: list[str]
    filters: str


class EntityLink(BaseModel):
    type: Literal["player", "game"]
    id: str
    label: str


class ReportPayload(BaseModel):
    """Final report shape enforced through Gemini structured output."""

    answer_markdown: str
    verdict: Literal[
        "Supported", "Mostly supported", "Mixed", "Misleading",
        "Not supported", "Insufficient evidence",
    ] | None
    key_findings: list[Finding]
    counterevidence: list[str]
    data_scope: DataScope
    links: list[EntityLink]
    confidence: Literal["high", "medium", "low"]

SYSTEM_PROMPT = f"""You are the research assistant inside "NBA Stat Analyzer".
You answer NBA questions using ONLY numbers returned by your tools, never from
memory. The current NBA season is {{season}} (today: {{today}}).

Rules:
- Resolve player names to IDs with search_player before other tools.
- NEVER state a statistic you did not get from a tool this conversation.
- Actively look for counterevidence before concluding; report it honestly.
- Always mention sample sizes; below ~10 games, say the evidence is weak. If
  data is unavailable or insufficient, say so plainly instead of guessing.
- EARLY IN A SEASON: if the current season has fewer than ~15 games for the
  subject (or a tool result includes a small-sample "note"), ALSO call the
  same tool for the previous season (get_previous_season gives its string),
  base your answer mainly on the fuller season, and label which season each
  number comes from.
- Comparisons: name who is better per category; never declare someone
  universally better unless the evidence is lopsided across the board.
- Claim verification: restate the claim as a measurable definition, gather
  evidence, a baseline, and counterexamples, then give a verdict from:
  {", ".join(VERDICTS)}.
- Tone: sharp, neutral basketball analyst. Briefly explain advanced stats on
  first use. Never use em dashes; use commas, colons, or periods.

The response schema is enforced separately. Write 2-6 short paragraphs or
bullets in answer_markdown, use null verdict outside claim checks, put exact
supporting numbers in key_findings, include honest caveats in counterevidence,
fully populate data_scope, and include a link for every player and game you
analyzed."""


_TOOLS_BY_MODE = {
    "player": [
        tools.search_player, tools.get_player_stats,
        tools.get_player_percentiles, tools.get_shot_profile, tools.get_trends,
        tools.get_career, tools.find_similar_players, tools.get_game_log,
        tools.get_on_off_impact, tools.get_previous_season,
        tools.get_elimination_game_stats, tools.get_shot_quality,
    ],
    "claim": [
        tools.search_player, tools.get_player_stats,
        tools.get_player_percentiles, tools.get_shot_profile, tools.get_trends,
        tools.get_career, tools.compare_players, tools.league_query,
        tools.get_game_log, tools.get_on_off_impact, tools.get_previous_season,
        tools.get_elimination_game_stats, tools.get_shot_quality,
    ],
    "compare": [
        tools.search_player, tools.compare_players, tools.get_player_stats,
        tools.get_player_percentiles, tools.get_shot_profile, tools.get_trends,
        tools.get_previous_season, tools.get_shot_quality,
    ],
    "game": [tools.list_games, tools.investigate_game],
}

_request_locks: dict[str, threading.Lock] = {}
_request_locks_guard = threading.Lock()


class AiUnavailable(Exception):
    pass


class AiRateLimited(Exception):
    pass


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def tools_for_mode(mode: str) -> list:
    """Return only the function declarations relevant to an explicit mode."""
    return _TOOLS_BY_MODE.get(mode, tools.ALL_TOOLS)


def _cache_key(question: str, mode: str, context: dict | None,
               model: str) -> str:
    normalized = {
        "prompt_version": PROMPT_VERSION,
        "season": current_season(),
        "model": model,
        "question": " ".join(question.lower().split()).rstrip("?!. "),
        "mode": mode,
        "context": context or {},
    }
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                     default=str)
    return "ai-report:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _request_lock(key: str) -> threading.Lock:
    """Coalesce identical in-flight requests in this backend process."""
    with _request_locks_guard:
        return _request_locks.setdefault(key, threading.Lock())


def _cached_report(key: str) -> dict | None:
    if os.environ.get("AI_RESPONSE_CACHE", "1").lower() in {"0", "false", "no"}:
        return None
    hit = cache.get(key)
    if not isinstance(hit, dict):
        return None
    report = deepcopy(hit)
    report["cached"] = True
    report["model_attempts"] = 0
    report.pop("api_attempts", None)  # remove metadata from pre-upgrade cache entries
    return report


def _store_report(key: str, report: dict) -> None:
    if os.environ.get("AI_RESPONSE_CACHE", "1").lower() in {"0", "false", "no"}:
        return
    ttl = _positive_int_env("AI_RESPONSE_CACHE_TTL", DEFAULT_CACHE_TTL_SECONDS)
    cache.set(key, report, ttl)


def _usage(response) -> dict:
    """Stable, JSON-friendly subset of the SDK's usage metadata."""
    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return {}
    fields = {
        "input_tokens": "prompt_token_count",
        "output_tokens": "candidates_token_count",
        "thinking_tokens": "thoughts_token_count",
        "tool_prompt_tokens": "tool_use_prompt_token_count",
        "cached_input_tokens": "cached_content_token_count",
        "total_tokens": "total_token_count",
    }
    return {
        label: value for label, attr in fields.items()
        if (value := getattr(metadata, attr, None)) is not None
    }


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


def _response_text(response) -> str:
    """Read text parts without SDK warnings about adjacent function calls."""
    chunks: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            if text := getattr(part, "text", None):
                chunks.append(text)
    return "".join(chunks)


def _generate_report(question: str, mode: str, context: dict | None,
                     requested_model: str) -> dict:
    from google.genai import errors, types

    client = _client()
    model = requested_model

    prompt_parts = [f"Investigation type: {mode}." if mode != "auto" else "",
                    f"Question: {question}"]
    if context:
        prompt_parts.append(
            "Context from the page the user came from (use these IDs directly): "
            + json.dumps(context))
    prompt = "\n".join(p for p in prompt_parts if p)

    system = SYSTEM_PROMPT.format(season=current_season(),
                                  today=datetime.now().strftime("%Y-%m-%d"))

    # Use one stable, efficient fallback. Each extra candidate can consume a
    # separate free-tier request, so aliases and retired 2.x models are omitted.
    candidates = [model, "gemini-3.1-flash-lite"]
    available_tools = tools_for_mode(mode)
    max_remote_calls = _positive_int_env(
        "AI_MAX_REMOTE_CALLS", DEFAULT_MAX_REMOTE_CALLS)
    max_output_tokens = _positive_int_env(
        "AI_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)
    thinking_level = os.environ.get("AI_THINKING_LEVEL", "low").lower()
    if thinking_level not in {"minimal", "low", "medium", "high"}:
        thinking_level = "low"
    model_attempts = 0

    def _attempt(candidate: str):
        nonlocal model_attempts
        model_attempts += 1
        return client.models.generate_content(
            model=candidate,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=available_tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=max_remote_calls),
                response_mime_type="application/json",
                response_schema=ReportPayload,
                max_output_tokens=max_output_tokens,
                thinking_config=types.ThinkingConfig(
                    thinking_level=thinking_level),
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
                "midnight Pacific time, so AI Mode will work again tomorrow. "
                "All other app features keep working.")
        if getattr(last_err, "code", None) == 429 or "429" in err_text:
            raise AiRateLimited(
                "The free Gemini tier is rate-limited right now. Wait about "
                "a minute and ask again.")
        raise AiRateLimited(
            "Google's AI servers are overloaded right now (temporary, their "
            "side). Wait a minute and ask again; the app automatically tries "
            "backup models.")

    report = _extract_json(_response_text(response))
    report.setdefault("key_findings", [])
    report.setdefault("counterevidence", [])
    report.setdefault("data_scope", {})
    report.setdefault("links", [])
    report["tool_trace"] = _tool_trace(response)
    report["model"] = model
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["usage"] = _usage(response)
    report["model_attempts"] = model_attempts
    report["cached"] = False
    return report


def ask(question: str, mode: str = "auto",
        context: dict | None = None) -> dict:
    """Run an investigation, reusing identical successful reports for 12h."""
    question = " ".join(question.split())
    if not question:
        raise ValueError("question cannot be empty")
    if mode not in {"auto", "player", "claim", "compare", "game"}:
        raise ValueError(f"unknown AI mode '{mode}'")

    # A game page supplies an exact game ID, so this route is unambiguous and
    # needs only the two game tools even if the UI is still set to Auto.
    effective_mode = (
        "game" if mode == "auto" and context and context.get("game_id") else mode
    )

    requested_model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    key = _cache_key(question, effective_mode, context, requested_model)
    if hit := _cached_report(key):
        return hit

    # The second cache check makes concurrent duplicates wait for and reuse the
    # first result rather than spending two free-tier requests.
    with _request_lock(key):
        if hit := _cached_report(key):
            return hit
        report = _generate_report(
            question, effective_mode, context, requested_model)
        _store_report(key, report)
        return report
