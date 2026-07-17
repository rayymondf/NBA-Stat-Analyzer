import json
import sys
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(EVAL_DIR))

from graders import grade_report, grounded_number_ratio, validate_case  # noqa: E402
from app.ai import orchestrator, tools  # noqa: E402


class EvalGraderTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "id": "fixture",
            "question": "Is the player efficient?",
            "mode": "claim",
            "tool_policy": {
                "required": ["search_player", "get_player_stats"],
                "one_of": [],
                "forbidden": ["investigate_game"],
                "max_calls": 2,
            },
            "report_policy": {
                "verdict_required": True,
                "min_findings": 1,
                "counterevidence_required": True,
            },
        }
        self.report = {
            "answer_markdown": "He posted 61.0% TS across 72 games.",
            "verdict": "Supported",
            "key_findings": [{"claim": "Efficient", "evidence": "61.0% TS in 72 games"}],
            "counterevidence": ["Volume was 20 attempts per game."],
            "data_scope": {
                "seasons": ["2025-26"],
                "sample": "72 games",
                "definitions": ["TS% includes free throws"],
                "filters": "none",
            },
            "links": [{"type": "player", "id": "1", "label": "Player"}],
            "confidence": "high",
            "tool_trace": [
                {"tool": "search_player", "args": {"name": "Player"},
                 "result": [{"player_id": 1, "name": "Player"}]},
                {"tool": "get_player_stats", "args": {"player_id": 1},
                 "result": {"games": 72, "shooting": {"ts_pct": 0.61},
                            "per_game": {"fga": 20}}},
            ],
            "usage": {"total_tokens": 500},
            "cached": False,
        }

    def test_well_grounded_report_passes(self):
        grade = grade_report(self.case, self.report)
        failures = [check for check in grade["checks"] if not check["passed"]]
        self.assertEqual(failures, [])
        self.assertTrue(grade["passed"])

    def test_untraceable_number_is_detected(self):
        self.report["answer_markdown"] += " He also averaged 44.4 assists."
        ratio, unsupported = grounded_number_ratio(self.report)
        self.assertLess(ratio, 0.9)
        self.assertIn("44.4", unsupported)

    def test_duplicate_tool_call_is_detected(self):
        self.report["tool_trace"].append(self.report["tool_trace"][-1].copy())
        grade = grade_report(self.case, self.report)
        duplicate = next(check for check in grade["checks"]
                         if check["name"] == "duplicate_calls")
        self.assertFalse(duplicate["passed"])

    def test_all_committed_cases_are_valid_and_routable(self):
        payload = json.loads((EVAL_DIR / "cases.json").read_text(encoding="utf-8"))
        all_names = {tool.__name__ for tool in tools.ALL_TOOLS}
        for case in payload["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(validate_case(case, all_names), [])
                routed = {tool.__name__ for tool in orchestrator.tools_for_mode(case["mode"])}
                self.assertTrue(set(case["tool_policy"].get("required", [])) <= routed)
                for group in case["tool_policy"].get("one_of", []):
                    self.assertTrue(any(name in routed for name in group))


if __name__ == "__main__":
    unittest.main()
