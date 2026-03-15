"""
Payment agent: uses a fast LLM with tool-calling. Records every tool invocation
so you can test efficacy, safety, and guardrails and see exactly when tools are called.
"""
from typing import Any

from .tools import TOOLS, run_tool
from .utils import get_openai_client

DEFAULT_MODEL = __import__("os").environ.get("PAYMENT_AGENT_MODEL", "gpt-3.5-turbo")

SYSTEM_PROMPT = """You are a Stripe-powered payment and finance assistant. You have these tools at your disposal:

- **Payments**: process_payment — one-time payments (amount in cents, currency, description).
- **Balance**: get_balance — see current available and pending balance (use when user asks if money is there or how much they have).
- **Add test balance**: add_test_balance — add money to the test account by charging a test card (test mode only; use when user wants to fund or top up their balance).
- **Payouts**: create_payout, list_payouts — send funds to bank; view payout history.
- **Transfers**: create_transfer, list_transfers — move money to another Stripe (Connect) account; view transfers.
- **Issuing**: create_issuing_card, list_issuing_cards — create virtual/physical cards; list cards (need cardholder ID).
- **Financial Connections**: list_financial_connection_accounts — list linked bank accounts.
- **Invoices**: create_invoice, list_invoices, finalize_invoice — create draft invoices, list them, finalize for payment.

All tools call Stripe directly; results match the Dashboard. Use the tool that matches the user's intent. Only call a tool when the user has given enough info (e.g. amount, currency, customer ID where required). For list/get tools you can use defaults. After each tool call, summarize the result in plain language. Do not call payment/payout/transfer/create tools for simple questions like balance or history—use the list_* tools instead."""


class ToolCallRecord:
    """Single record of a tool having been called (for testing and observability)."""
    def __init__(self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]):
        self.tool_name = tool_name
        self.arguments = arguments
        self.result = result

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
        }


class PaymentAgent:
    """
    Agent that uses an LLM with a process_payment tool. Run with .run() to get
    the final reply and .tool_calls_log to inspect every tool invocation (for
    efficacy, safety, and guardrail testing).
    """
    def __init__(self, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        self._client = None
        self.tool_calls_log: list[ToolCallRecord] = []

    @property
    def client(self):
        if self._client is None:
            self._client = get_openai_client()
        return self._client

    def run(self, user_id: str, user_message: str) -> dict[str, Any]:
        """
        Run the agent for one user turn. Returns {
            "reply": str,
            "tool_calls_log": [{"tool_name", "arguments", "result"}, ...]
        }. The log is also stored on self.tool_calls_log and cleared at the start of each run.
        """
        self.tool_calls_log = []
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"[user_id: {user_id}]\n\n{user_message}"},
        ]
        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=512,
                temperature=0.1,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return {
                    "reply": (msg.content or "").strip(),
                    "tool_calls_log": [r.to_dict() for r in self.tool_calls_log],
                }
            messages.append(msg)
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    import json as _json
                    args = _json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = run_tool(name, args)
                self.tool_calls_log.append(ToolCallRecord(name, args, result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": __import__("json").dumps(result),
                })
        return {
            "reply": "I hit the tool-call limit; please try again.",
            "tool_calls_log": [r.to_dict() for r in self.tool_calls_log],
        }


def run_payment_agent(user_id: str, user_message: str, model: str | None = None) -> dict[str, Any]:
    """One-shot: run the payment agent and return reply + tool_calls_log."""
    agent = PaymentAgent(model=model)
    return agent.run(user_id=user_id, user_message=user_message)
