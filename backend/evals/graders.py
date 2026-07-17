"""Deterministic graders for NBA AI reports.

These checks intentionally avoid using a second language model, so grading is
repeatable and costs no Gemini quota.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable


REPORT_FIELDS = {
    "answer_markdown", "verdict", "key_findings", "counterevidence",
    "data_scope", "links", "confidence", "tool_trace",
}
VALID_MODES = {"auto", "player", "claim", "compare", "game"}
VALID_VERDICTS = {
    "Supported", "Mostly supported", "Mixed", "Misleading",
    "Not supported", "Insufficient evidence",
}


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def validate_case(case: dict, available_tool_names: set[str]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "question", "mode", "tool_policy", "report_policy"):
        if field not in case:
            errors.append(f"missing '{field}'")
    if errors:
        return errors
    if case["mode"] not in VALID_MODES:
        errors.append(f"unknown mode '{case['mode']}'")
    if not isinstance(case["question"], str) or not case["question"].strip():
        errors.append("question must be non-empty text")

    policy = case["tool_policy"]
    referenced = set(policy.get("required", [])) | set(policy.get("forbidden", []))
    for group in policy.get("one_of", []):
        referenced.update(group)
    unknown = referenced - available_tool_names
    if unknown:
        errors.append(f"unknown tools: {', '.join(sorted(unknown))}")
    overlap = set(policy.get("required", [])) & set(policy.get("forbidden", []))
    if overlap:
        errors.append(f"tools both required and forbidden: {', '.join(sorted(overlap))}")
    if int(policy.get("max_calls", 0)) < 0:
        errors.append("max_calls cannot be negative")
    return errors


def _numeric_values(value) -> list[float]:
    values: list[float] = []
    if isinstance(value, bool) or value is None:
        return values
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        return [float(token.rstrip("%"))
                for token in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?%?", value)]
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_numeric_values(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_numeric_values(item))
    return values


def _narrative_numbers(report: dict) -> list[tuple[float, bool, str]]:
    pieces = [report.get("answer_markdown", "")]
    pieces.extend(str(item.get("evidence", ""))
                  for item in report.get("key_findings", [])
                  if isinstance(item, dict))
    pieces.extend(str(item) for item in report.get("counterevidence", []))
    text = "\n".join(pieces)
    found: list[tuple[float, bool, str]] = []
    for match in re.finditer(r"(?<![\w.])-?\d+(?:\.\d+)?%?", text):
        token = match.group(0)
        percent = token.endswith("%")
        number = float(token.rstrip("%"))
        # Years and likely entity IDs are metadata, not statistical claims.
        if not percent and (1900 <= abs(number) <= 2100 or abs(number) > 1000):
            continue
        found.append((number, percent, token))
    return found


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.051, abs(a) * 0.002)


def grounded_number_ratio(report: dict) -> tuple[float | None, list[str]]:
    tool_numbers: list[float] = []
    for call in report.get("tool_trace", []):
        if isinstance(call, dict) and "result" in call:
            tool_numbers.extend(_numeric_values(call["result"]))
    claims = _narrative_numbers(report)
    if not claims:
        return 1.0, []
    if not tool_numbers:
        return None, [token for _, _, token in claims]

    unsupported: list[str] = []
    for number, percent, token in claims:
        candidates = [number]
        if percent:
            candidates.append(number / 100)
        supported = any(_close(candidate, tool_number)
                        for candidate in candidates for tool_number in tool_numbers)
        if not supported:
            unsupported.append(token)
    return (len(claims) - len(unsupported)) / len(claims), unsupported


def grade_report(case: dict, report: dict) -> dict:
    checks: list[dict] = []
    missing = REPORT_FIELDS - set(report)
    checks.append(_check("report_schema", not missing,
                         "complete" if not missing else f"missing {sorted(missing)}"))

    trace = report.get("tool_trace", [])
    trace_ok = isinstance(trace, list) and all(
        isinstance(call, dict) and isinstance(call.get("tool"), str)
        and isinstance(call.get("args", {}), dict) for call in trace)
    checks.append(_check("tool_trace_shape", trace_ok,
                         f"{len(trace) if isinstance(trace, list) else 0} recorded calls"))
    calls = [call.get("tool") for call in trace if isinstance(call, dict)]
    policy = case["tool_policy"]

    required = policy.get("required", [])
    missing_required = [name for name in required if name not in calls]
    checks.append(_check("required_tools", not missing_required,
                         "present" if not missing_required else f"missing {missing_required}"))

    one_of_failures = [group for group in policy.get("one_of", [])
                       if not any(name in calls for name in group)]
    checks.append(_check("alternative_tools", not one_of_failures,
                         "satisfied" if not one_of_failures else f"missing one of {one_of_failures}"))

    forbidden_used = [name for name in policy.get("forbidden", []) if name in calls]
    checks.append(_check("forbidden_tools", not forbidden_used,
                         "none" if not forbidden_used else f"used {forbidden_used}"))

    max_calls = int(policy.get("max_calls", 999))
    checks.append(_check("tool_budget", len(calls) <= max_calls,
                         f"{len(calls)}/{max_calls} calls"))
    signatures = [json.dumps({"tool": call.get("tool"), "args": call.get("args", {})},
                             sort_keys=True, default=str)
                  for call in trace if isinstance(call, dict)]
    duplicate_count = len(signatures) - len(set(signatures))
    checks.append(_check("duplicate_calls", duplicate_count == 0,
                         f"{duplicate_count} exact duplicates"))

    report_policy = case["report_policy"]
    verdict = report.get("verdict")
    verdict_valid = verdict is None or verdict in VALID_VERDICTS
    if report_policy.get("verdict_required"):
        verdict_valid = verdict in VALID_VERDICTS
    allowed = report_policy.get("allowed_verdicts")
    if allowed:
        verdict_valid = verdict in allowed
    checks.append(_check("verdict", verdict_valid, str(verdict)))

    findings = report.get("key_findings", [])
    min_findings = int(report_policy.get("min_findings", 0))
    findings_ok = isinstance(findings, list) and len(findings) >= min_findings
    checks.append(_check("evidence", findings_ok,
                         f"{len(findings) if isinstance(findings, list) else 0}/{min_findings} findings"))

    counter = report.get("counterevidence", [])
    counter_ok = isinstance(counter, list)
    if report_policy.get("counterevidence_required"):
        counter_ok = counter_ok and len(counter) > 0
    checks.append(_check("counterevidence", counter_ok,
                         f"{len(counter) if isinstance(counter, list) else 0} items"))

    scope = report.get("data_scope", {})
    scope_ok = isinstance(scope, dict) and bool(scope.get("seasons")) and bool(scope.get("sample"))
    checks.append(_check("data_scope", scope_ok,
                         "season and sample present" if scope_ok else "season/sample missing"))

    ratio, unsupported = grounded_number_ratio(report)
    grounding_ok = ratio is not None and ratio >= 0.9
    detail = ("no tool results available" if ratio is None else
              f"{ratio:.0%} traced" + (f"; unmatched {unsupported[:8]}" if unsupported else ""))
    checks.append(_check("numeric_grounding", grounding_ok, detail))

    passed = sum(check["passed"] for check in checks)
    return {
        "case_id": case["id"],
        "score": round(100 * passed / len(checks), 1),
        "passed": passed == len(checks),
        "checks": checks,
        "metrics": {
            "tool_calls": len(calls),
            "duplicate_calls": duplicate_count,
            "grounded_number_ratio": ratio,
            "total_tokens": (report.get("usage") or {}).get("total_tokens"),
            "elapsed_seconds": report.get("elapsed_seconds"),
            "cached": report.get("cached", False),
        },
    }


def summarize(grades: Iterable[dict]) -> dict:
    grades = list(grades)
    check_totals: dict[str, list[int]] = {}
    for grade in grades:
        for check in grade["checks"]:
            counts = check_totals.setdefault(check["name"], [0, 0])
            counts[0] += int(check["passed"])
            counts[1] += 1
    return {
        "cases": len(grades),
        "fully_passed": sum(grade["passed"] for grade in grades),
        "average_score": round(sum(grade["score"] for grade in grades) / len(grades), 1)
        if grades else 0,
        "checks": {name: {"passed": counts[0], "total": counts[1]}
                   for name, counts in sorted(check_totals.items())},
        "total_tokens": sum(
            grade["metrics"].get("total_tokens") or 0 for grade in grades),
        "new_tokens": sum(
            grade["metrics"].get("total_tokens") or 0 for grade in grades
            if not grade["metrics"].get("cached")),
        "cached_cases": sum(bool(grade["metrics"].get("cached")) for grade in grades),
        "total_tool_calls": sum(grade["metrics"]["tool_calls"] for grade in grades),
    }
