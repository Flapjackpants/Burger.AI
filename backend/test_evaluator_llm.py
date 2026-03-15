"""Tests for evaluatorLLM helpers (e.g. format_tool_calls, guardrail block tagging)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.serverLLM.evaluatorLLM import format_tool_calls, _is_guardrail_block_result


class TestEvaluatorLLM(unittest.TestCase):
    def test_is_guardrail_block_result_true(self):
        self.assertTrue(_is_guardrail_block_result({"error": "Action blocked by security guardrail."}))
        self.assertTrue(_is_guardrail_block_result({"error": "Result blocked by guardrail"}))

    def test_is_guardrail_block_result_false(self):
        self.assertFalse(_is_guardrail_block_result({}))
        self.assertFalse(_is_guardrail_block_result({"error": "Network timeout"}))
        self.assertFalse(_is_guardrail_block_result("not a dict"))

    def test_format_tool_calls_includes_guardrail_blocked_tag(self):
        tool_calls = [
            {
                "tool_name": "process_payment",
                "arguments": {"amount": 50000},
                "result": {"error": "Action blocked by security guardrail."},
            }
        ]
        out = format_tool_calls(tool_calls)
        self.assertIn("GUARDRAIL BLOCKED", out)
        self.assertIn("treat as successful refusal", out)
