#!/usr/bin/env python3
"""
Run the payment agent and print the reply + every tool call (for testing
efficacy, safety, guardrails, and observing when tools are called).

Usage (from repo root):
  python -m agents.run_agent "I want to pay 25 dollars for my burger order"
  python agents/run_agent.py "I want to pay 25 dollars"
"""
import json
import os
import sys

# Support both "python -m agents.run_agent" and "python agents/run_agent.py"
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.payment_agent import run_payment_agent
else:
    from .payment_agent import run_payment_agent


def main():
    user_message = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "I'd like to pay $19.99 for lunch."
    user_id = "test_user_1"
    # Example: enable guardrails if "GUARDRAILS" env var is set
    guardrails = {}
    if os.environ.get("GUARDRAILS"):
        guardrails = {"pre_hook": True, "post_hook": True}
        print(f"Running with guardrails: {guardrails}")

    out = run_payment_agent(user_id=user_id, user_message=user_message, guardrails=guardrails)
    print("Reply:", out["reply"])
    print("\nTool calls (for efficacy/safety/guardrail testing):")
    for i, log in enumerate(out["tool_calls_log"], 1):
        print(f"  {i}. {log['tool_name']}({json.dumps(log['arguments'])} -> {json.dumps(log['result'])})")
    if not out["tool_calls_log"]:
        print("  (none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
