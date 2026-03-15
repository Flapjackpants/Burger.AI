
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the actual Agent and Guardrail Logic
from agents.payment_agent import run_payment_agent, ToolCallRecord, PaymentAgent
from backend.serverLLM.guardrailLLM import generate_guardrails

class TestGuardrailIntegration(unittest.TestCase):

    def test_dynamic_guardrail_pre_hook(self):
        """
        Test that the schema defined in GuardrailLLM is actually executable by PaymentAgent.
        """
        print("\n--- Testing Guardrail Execution Engine: PRE-HOOK ---")

        # 1. Simulate the LLM output (A Dynamic Rule)
        generated_rules = [
            {
                "type": "pre_hook",
                "tool_name": "process_payment",
                "condition": "args['amount'] > 5000",
                "action": "block",
                "message": "AI_GENERATED_BLOCK: Amount too high!"
            }
        ]
        
        # 2. Setup Agent
        agent = PaymentAgent()
        agent._client = MagicMock()
        
        # When mocking pydantic-like objects or OpenAI objects, attributes like .function.name
        # need to be set specifically, otherwise MagicMock creates a new mock for them.
        
        mock_tool_function = MagicMock()
        mock_tool_function.name = "process_payment"
        mock_tool_function.arguments = '{"amount": 6000, "currency": "usd"}'
        
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function = mock_tool_function
        
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool_call]
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_msg)]
        agent._client.chat.completions.create.return_value = mock_response

        # 3. Execute
        # Note: run() loops 5 times if tool calls keep happening.
        # If the guardrail blocks it, it returns a tool result with error.
        # The agent then sees that error and might try again or apologize.
        # We just want to check the log of the first attempt.
        result = agent.run(user_id="test_user", user_message="Pay 60", guardrails=generated_rules)
        
        # 4. Validation
        logs = result["tool_calls_log"]
        # Convert logs to simple dicts if they are objects
        logs_serializable = [l.to_dict() if hasattr(l, 'to_dict') else l for l in logs]
        
        print(f"Tool Logs: {logs_serializable} -- LENGTH: {len(logs_serializable)}")
        
        # Check first log
        first_log = logs_serializable[0]
        # Verify name is string "process_payment"
        self.assertEqual(first_log["tool_name"], "process_payment")
        
        result_data = first_log["result"]
        
        self.assertIn("error", result_data, f"Result should contain error, got {result_data}")
        self.assertEqual(result_data["error"], "AI_GENERATED_BLOCK: Amount too high!", "Message match")
        
        print("SUCCESS: Pre-hook rule successfully blocked the tool call.")

    @patch("agents.payment_agent.run_tool")
    def test_dynamic_guardrail_post_hook(self, mock_run_tool):
        """Test POST-HOOK redaction"""
        print("\n--- Testing Guardrail Execution Engine: POST-HOOK ---")
        
        # 1. Setup Rule
        generated_rules = [{
            "type": "post_hook",
            "tool_name": "get_balance",
            "condition": "'secret' in str(result)",
            "action": "redact_field",
            "target_field": "secret",
            "replacement": "[REDACTED_BY_AI]"
        }]
        
        # 2. Setup Agent
        agent = PaymentAgent()
        agent._client = MagicMock()
        
        # Mock LLM calling get_balance
        mock_tool_function = MagicMock()
        mock_tool_function.name = "get_balance"
        mock_tool_function.arguments = '{}'
        
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_456"
        mock_tool_call.function = mock_tool_function
        
        mock_msg = MagicMock()
        mock_msg.tool_calls = [mock_tool_call]
        
        agent._client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_msg)])
        
        # Mock Tool Execution returning sensitive data
        mock_run_tool.return_value = {"balance": 100, "secret": "s3cr3t_k3y_xyz"}
        
        # 3. Execute
        result = agent.run(user_id="test", user_message="check bal", guardrails=generated_rules)
        
        # 4. Validation
        logs = result["tool_calls_log"]
        logs_serializable = [l.to_dict() if hasattr(l, 'to_dict') else l for l in logs]
        final_output = logs_serializable[0]["result"]
        
        print(f"Tool Output: {final_output}")
        self.assertEqual(final_output.get("secret"), "[REDACTED_BY_AI]", "Secret should be redacted")
        self.assertEqual(final_output.get("balance"), 100, "Non-sensitive data should remain")
        
        print("SUCCESS: Post-hook rule successfully redacted the data.")

if __name__ == "__main__":
    unittest.main()
