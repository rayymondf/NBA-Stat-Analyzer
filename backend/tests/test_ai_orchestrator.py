import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import orchestrator, tools


class OrchestratorTests(unittest.TestCase):
    def test_explicit_modes_expose_fewer_tools(self):
        self.assertEqual(
            [tool.__name__ for tool in orchestrator.tools_for_mode("game")],
            ["list_games", "investigate_game"],
        )
        self.assertLess(len(orchestrator.tools_for_mode("compare")), len(tools.ALL_TOOLS))
        self.assertEqual(orchestrator.tools_for_mode("auto"), tools.ALL_TOOLS)

    def test_auto_mode_uses_compact_route_for_player_context(self):
        self.assertEqual(
            orchestrator._effective_mode("How efficient has he been?", "auto", {"player_id": 23}),
            "player",
        )
        self.assertEqual(
            orchestrator._effective_mode("Compare them", "auto", None), "compare"
        )

    @patch("app.ai.orchestrator._store_report")
    @patch("app.ai.orchestrator._generate_report")
    @patch("app.ai.orchestrator._cached_report", return_value=None)
    def test_player_context_does_not_prefetch_before_timed_generation(
            self, _cached, generate, _store):
        generate.return_value = {"answer_markdown": "ok"}
        with patch("app.ai.orchestrator.tools.get_player_stats") as stats:
            orchestrator.ask("Is he efficient?", "auto", {
                "player_id": 23, "season": "2026-27", "season_type": "Pre Season",
            })
        stats.assert_not_called()
        self.assertEqual(generate.call_args.args[1], "player")

    def test_preseason_is_valid_for_ai_tools(self):
        self.assertEqual(tools._season_type("Pre Season"), "Pre Season")


    def test_cache_key_normalizes_question_case_and_whitespace(self):
        first = orchestrator._cache_key(" Is  Tatum efficient? ", "claim", None, "model")
        second = orchestrator._cache_key("is tatum EFFICIENT?", "claim", {}, "model")
        self.assertEqual(first, second)

    def test_extract_json_accepts_fenced_response(self):
        payload = orchestrator._extract_json('```json\n{"answer_markdown":"ok"}\n```')
        self.assertEqual(payload["answer_markdown"], "ok")

    def test_usage_metadata_is_normalized(self):
        response = SimpleNamespace(usage_metadata=SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=30,
            thoughts_token_count=12,
            tool_use_prompt_token_count=40,
            cached_content_token_count=5,
            total_token_count=182,
        ))
        self.assertEqual(orchestrator._usage(response)["total_tokens"], 182)
        self.assertEqual(orchestrator._usage(response)["thinking_tokens"], 12)

    def test_response_text_ignores_function_call_parts(self):
        response = SimpleNamespace(candidates=[SimpleNamespace(
            content=SimpleNamespace(parts=[
                SimpleNamespace(text=None, function_call=object()),
                SimpleNamespace(text='{"answer_markdown":"ok"}'),
            ]),
        )])
        self.assertEqual(orchestrator._response_text(response),
                         '{"answer_markdown":"ok"}')

    @patch("app.ai.orchestrator._cached_report")
    def test_cached_answer_skips_generation(self, cached_report):
        cached_report.return_value = {
            "answer_markdown": "cached", "cached": True, "model_attempts": 0,
        }
        with patch("app.ai.orchestrator._generate_report") as generate:
            report = orchestrator.ask("Is this cached?", "auto")
        self.assertTrue(report["cached"])
        self.assertEqual(report["model_attempts"], 0)
        generate.assert_not_called()

    def test_invalid_mode_is_rejected_before_api_call(self):
        with self.assertRaises(ValueError):
            orchestrator.ask("Question", "invalid")

    def test_request_lock_entry_is_removed_after_use(self):
        key = "test-lock-cleanup"
        with orchestrator._request_lock(key):
            self.assertIn(key, orchestrator._request_locks)
        self.assertNotIn(key, orchestrator._request_locks)

    def test_tool_inputs_are_bounded_before_service_calls(self):
        invalid_calls = (
            lambda: tools.search_player("x"),
            lambda: tools.get_player_stats(0),
            lambda: tools.get_player_stats(1, season="2025-99"),
            lambda: tools.league_query("leaders", limit=10_000),
            lambda: tools.list_games(team="NOT-A-TEAM"),
            lambda: tools.investigate_game("123"),
        )
        for invalid_call in invalid_calls:
            with self.subTest(call=invalid_call), self.assertRaises(ValueError):
                invalid_call()

    @patch("app.ai.orchestrator._store_report")
    @patch("app.ai.orchestrator._generate_report")
    @patch("app.ai.orchestrator._cached_report", return_value=None)
    def test_auto_game_context_uses_game_route(self, _cached, generate, _store):
        generate.return_value = {"answer_markdown": "ok"}
        orchestrator.ask("Why did they lose?", "auto", {"game_id": "123"})
        self.assertEqual(generate.call_args.args[1], "game")

    @patch("app.ai.orchestrator._store_report")
    @patch("app.ai.orchestrator._generate_report")
    @patch("app.ai.orchestrator._cached_report", return_value=None)
    def test_failed_report_refunds_global_budget(self, _cached, generate, _store):
        # A failed Gemini call must release its reserved budget slot; otherwise
        # a burst of upstream errors exhausts the per-minute budget and locks
        # out AI Mode without a single successful report.
        orchestrator._report_budget.clear()
        generate.side_effect = RuntimeError("gemini exploded")
        with self.assertRaises(RuntimeError):
            orchestrator.ask("Any question?", "auto")
        self.assertEqual(len(orchestrator._report_budget), 0)

    @patch("app.ai.orchestrator._store_report")
    @patch("app.ai.orchestrator._generate_report")
    @patch("app.ai.orchestrator._cached_report", return_value=None)
    def test_successful_report_keeps_budget_reservation(self, _cached, generate, _store):
        orchestrator._report_budget.clear()
        generate.return_value = {"answer_markdown": "ok"}
        orchestrator.ask("Another question?", "auto")
        self.assertEqual(len(orchestrator._report_budget), 1)


    def test_context_warm_is_noop_without_context(self):
        # No context -> no thread, no service call.
        with patch("app.services.frames.merged_logs") as merged:
            orchestrator._warm_context_cache("player", None)
        merged.assert_not_called()

    def test_context_warm_prefetches_player_logs_in_background(self):
        import threading as _threading
        done = _threading.Event()
        with patch("app.services.frames.merged_logs") as merged:
            merged.side_effect = lambda *a, **k: done.set()
            orchestrator._warm_context_cache("player", {"player_id": 23})
            # Fire-and-forget daemon thread; it should call merged_logs shortly.
            assert done.wait(timeout=5), "background warm did not call merged_logs"
        self.assertEqual(merged.call_args.args[0], 23)

    def test_context_warm_swallows_errors(self):
        import threading as _threading
        attempted = _threading.Event()
        def boom(*_a, **_k):
            attempted.set()
            raise RuntimeError("upstream down")
        with patch("app.services.frames.merged_logs", side_effect=boom):
            # Must not raise on the calling thread.
            orchestrator._warm_context_cache("claim", {"player_id": 7})
            assert attempted.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
