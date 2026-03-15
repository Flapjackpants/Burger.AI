"""
Payment agent: uses a fast LLM with tool-calling. Records every tool invocation
so you can test efficacy, safety, and guardrails and see exactly when tools are called.
"""
from typing import Any, Union, Optional

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
    def __init__(self, model: Union[str, None] = None):
        self.model = model or DEFAULT_MODEL
        self._client = None
        self.tool_calls_log: list[ToolCallRecord] = []

    @property
    def client(self):
        if self._client is None:
            self._client = get_openai_client()
        return self._client

    def run(self, user_id: str, user_message: str, guardrails: Optional[Any] = None) -> dict[str, Any]:
        """
        Run the agent for one user turn. Returns {
            "reply": str,
            "tool_calls_log": [{"tool_name", "arguments", "result"}, ...]
        }.
        
        guardrails: Can be:
          1. dict (Legacy/Hardcoded): {"pre_hook": bool, "post_hook": bool}
          2. list (Dynamic/AI-Generated): [{"type": "pre_hook", "condition": "...", ...}]
        """
        # unexpected types handling
        if guardrails is None:
            guardrails_config = {}
            dynamic_rules = []
        elif isinstance(guardrails, dict):
            guardrails_config = guardrails
            dynamic_rules = []
        elif isinstance(guardrails, list):
            guardrails_config = {}
            dynamic_rules = guardrails
        else:
            guardrails_config = {}
            dynamic_rules = []

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

                # -- 1. Dynamic Pre-Hook Rules --
                blocked_by_rule = False
                block_message = "Action blocked by security guardrail."
                
                for rule in dynamic_rules:
                    if rule.get("type") == "pre_hook":
                        # Check tool name
                        target_tool = rule.get("tool_name", "*")
                        if target_tool != "*" and target_tool != name:
                            continue
                        
                        # Evaluate condition
                        condition = rule.get("condition", "False")
                        try:
                            # Safe eval context
                            safe_locals = {"args": args, "tool_name": name}
                            if eval(condition, {"__builtins__": {}}, safe_locals):
                                blocked_by_rule = True
                                block_message = rule.get("message", block_message)
                                break
                        except Exception as e:
                            print(f"[Guardrail Check Error] {e}")

                if blocked_by_rule:
                     result = {"error": block_message}
                     self.tool_calls_log.append(ToolCallRecord(name, args, result))
                     messages.append({
                         "role": "tool",
                         "tool_call_id": tc.id,
                         "content": __import__("json").dumps(result),
                     })
                     continue

                # -- 2. Hardcoded Pre-Hook (Legacy) --
                if guardrails_config.get("pre_hook"):
                    if name == "process_payment" and args.get("amount", 0) > 10000: # >$100.00
                         result = {"error": "Guardrail Violation: Payment exceeds authorized limit of $100.00. Transaction blocked."}
                         self.tool_calls_log.append(ToolCallRecord(name, args, result))
                         messages.append({
                             "role": "tool",
                             "tool_call_id": tc.id,
                             "content": __import__("json").dumps(result),
                         })
                         continue

                result = run_tool(name, args)
                
                # -- 3. Dynamic Post-Hook Rules --
                for rule in dynamic_rules:
                    if rule.get("type") == "post_hook":
                         target_tool = rule.get("tool_name", "*")
                         if target_tool != "*" and target_tool != name:
                            continue
                         
                         condition = rule.get("condition", "False")
                         try:
                             safe_locals = {"args": args, "result": result, "tool_name": name, "str": str}
                             if eval(condition, {"__builtins__": {}, "str": str}, safe_locals):
                                 action = rule.get("action")
                                 if action == "block_result":
                                     result = {"error": rule.get("message", "Result blocked by guardrail")}
                                 elif action == "redact_field":
                                     target_field = rule.get("target_field")
                                     if isinstance(result, dict) and target_field in result:
                                         result[target_field] = rule.get("replacement", "<REDACTED>")
                         except Exception as e:
                             print(f"[Guardrail Post-Check Error] {e}")

                # -- 4. Hardcoded Post-Hook (Legacy) --
                if guardrails_config.get("post_hook"):
                    if isinstance(result, dict):
                        if "id" in result:
                            result["id"] = "<REDACTED_ID>"
                        if "customer" in result:
                            result["customer"] = "<REDACTED_PII>"

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


def run_payment_agent(user_id: str, user_message: str, model: Union[str, None] = None, guardrails: Union[dict[str, Any], None] = None) -> dict[str, Any]:
    """One-shot: run the payment agent and return reply + tool_calls_log."""
    agent = PaymentAgent(model=model)
    return agent.run(user_id=user_id, user_message=user_message, guardrails=guardrails)
