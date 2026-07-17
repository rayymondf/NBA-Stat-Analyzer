"""Run deterministic checks or a quota-conscious live NBA agent evaluation."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

from app.ai import orchestrator, tools  # noqa: E402
from graders import grade_report, summarize, validate_case  # noqa: E402

CASES_PATH = Path(__file__).with_name("cases.json")
RESULTS_DIR = Path(__file__).with_name("results")


def load_cases(selected: list[str] | None = None, limit: int | None = None) -> list[dict]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if selected:
        wanted = set(selected)
        cases = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            raise SystemExit(f"Unknown case IDs: {', '.join(sorted(missing))}")
    return cases[:limit] if limit else cases


def check_suite(cases: list[dict]) -> int:
    all_names = {tool.__name__ for tool in tools.ALL_TOOLS}
    failures = 0
    for case in cases:
        errors = validate_case(case, all_names)
        routed = {tool.__name__ for tool in orchestrator.tools_for_mode(case["mode"])}
        required = set(case["tool_policy"].get("required", []))
        alternatives = case["tool_policy"].get("one_of", [])
        unavailable = required - routed
        unavailable_groups = [group for group in alternatives
                              if not any(name in routed for name in group)]
        if unavailable:
            errors.append(f"mode does not expose required tools: {sorted(unavailable)}")
        if unavailable_groups:
            errors.append(f"mode does not expose alternatives: {unavailable_groups}")
        status = "PASS" if not errors else "FAIL"
        print(f"{status:4} {case['id']}")
        for error in errors:
            print(f"     {error}")
        failures += bool(errors)
    print(f"\nSuite check: {len(cases) - failures}/{len(cases)} valid; 0 Gemini requests")
    return 1 if failures else 0


def _save(payload: dict, output: Path | None) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = RESULTS_DIR / f"eval-{stamp}.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output


def _print_grades(grades: list[dict]) -> None:
    for grade in grades:
        status = "PASS" if grade["passed"] else "FAIL"
        metrics = grade["metrics"]
        tokens = metrics.get("total_tokens")
        token_text = f", {tokens} tokens" if tokens is not None else ""
        print(f"{status:4} {grade['case_id']}: {grade['score']:.1f}% "
              f"({metrics['tool_calls']} tools{token_text})")
        for check in grade["checks"]:
            if not check["passed"]:
                print(f"     {check['name']}: {check['detail']}")
    summary = summarize(grades)
    print(f"\nAgent eval: {summary['fully_passed']}/{summary['cases']} fully passed; "
          f"average {summary['average_score']:.1f}%")
    print(f"Usage: {summary['total_tool_calls']} tool calls, "
          f"{summary['new_tokens']} new tokens, {summary['cached_cases']} cached cases")


def run_live(cases: list[dict], delay: float, output: Path | None,
             fresh: bool) -> int:
    load_dotenv(BACKEND_DIR / ".env")
    if fresh:
        os.environ["AI_RESPONSE_CACHE"] = "0"
    print(f"LIVE EVAL: up to {len(cases)} Gemini investigations. "
          "Active limits vary by project/model; the run stops on any error.")
    records: list[dict] = []
    grades: list[dict] = []
    for index, case in enumerate(cases):
        if index and delay:
            time.sleep(delay)
        print(f"\n[{index + 1}/{len(cases)}] {case['id']}")
        started = time.perf_counter()
        try:
            report = orchestrator.ask(case["question"], case["mode"], case.get("context"))
            elapsed = round(time.perf_counter() - started, 3)
            report["elapsed_seconds"] = elapsed
            grade = grade_report(case, report)
            records.append({"case": case, "report": report, "grade": grade})
            grades.append(grade)
            print(f"     completed in {elapsed:.1f}s")
        except Exception as error:  # stop rather than spend quota retrying the suite
            elapsed = round(time.perf_counter() - started, 3)
            records.append({"case": case, "error": str(error),
                            "elapsed_seconds": elapsed})
            print(f"     stopped: {error}")
            break

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": os.environ.get("GEMINI_MODEL", "gemini-flash-latest"),
        "fresh": fresh,
        "records": records,
        "summary": summarize(grades),
    }
    saved = _save(payload, output)
    _print_grades(grades)
    print(f"Saved reusable results to {saved}")
    return 0 if grades and all(grade["passed"] for grade in grades) else 1


def grade_saved(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    grades = []
    for record in payload.get("records", []):
        if "report" in record:
            grade = grade_report(record["case"], record["report"])
            record["grade"] = grade
            grades.append(grade)
    _print_grades(grades)
    return 0 if grades and all(grade["passed"] for grade in grades) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--live", action="store_true",
                        help="call Gemini; omitted by default to protect free quota")
    action.add_argument("--responses", type=Path,
                        help="re-grade a saved live result without API calls")
    parser.add_argument("--case", action="append", dest="cases",
                        help="case ID to run (repeatable)")
    parser.add_argument("--limit", type=int,
                        help="maximum number of cases; recommended: 1 on free tier")
    parser.add_argument("--delay", type=float, default=15,
                        help="seconds between live cases (default: 15)")
    parser.add_argument("--fresh", action="store_true",
                        help="bypass the AI response cache; consumes fresh quota")
    parser.add_argument("--output", type=Path, help="live result JSON path")
    args = parser.parse_args()

    if args.responses:
        return grade_saved(args.responses)
    cases = load_cases(args.cases, args.limit)
    if args.live:
        return run_live(cases, args.delay, args.output, args.fresh)
    return check_suite(cases)


if __name__ == "__main__":
    raise SystemExit(main())
