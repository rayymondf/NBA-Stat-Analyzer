import unittest
import sys
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

    @patch("app.ai.orchestrator._store_report")
    @patch("app.ai.orchestrator._generate_report")
    @patch("app.ai.orchestrator._cached_report", return_value=None)
    def test_auto_game_context_uses_game_route(self, _cached, generate, _store):
        generate.return_value = {"answer_markdown": "ok"}
        orchestrator.ask("Why did they lose?", "auto", {"game_id": "123"})
        self.assertEqual(generate.call_args.args[1], "game")


if __name__ == "__main__":
    unittest.main()
