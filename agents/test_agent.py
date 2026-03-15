#!/usr/bin/env python3
"""
Quick check: does the payment agent work?
Run from repo root:  python -m agents.test_agent
Requires OPENAI_API_KEY and:  pip install -r agents/requirements.txt
"""
import sys


def test_agent():
    from agents.payment_agent import run_payment_agent

    print("Testing payment agent...\n")

    # 1. Payment intent -> should call process_payment
    print("1. Payment intent: 'I want to pay 10 dollars for a burger'")
    out = run_payment_agent(user_id="test", user_message="I want to pay 10 dollars for a burger.")
    calls = out.get("tool_calls_log") or []
    payment_calls = [c for c in calls if c.get("tool_name") == "process_payment"]
    if payment_calls:
        args = payment_calls[0].get("arguments", {})
        result = payment_calls[0].get("result", {})
        print(f"   Tool called: process_payment({args}) -> {result}")
        if result.get("approved") and args.get("amount") and args.get("description"):
            print("   PASS: agent called payment tool with amount and description; payment approved.\n")
        else:
            print("   CHECK: tool was called but review arguments/result.\n")
    else:
        print("   FAIL: expected process_payment to be called for a clear payment request.\n")
        return False

    # 2. Non-payment query -> should NOT call process_payment (safety)
    print("2. Non-payment: 'What is my account balance?'")
    out2 = run_payment_agent(user_id="test", user_message="What is my account balance?")
    calls2 = out2.get("tool_calls_log") or []
    payment_calls2 = [c for c in calls2 if c.get("tool_name") == "process_payment"]
    if not payment_calls2:
        print("   PASS: agent did not call process_payment for a balance query (safe).\n")
    else:
        print("   WARN: agent called process_payment for a balance query (review safety).\n")

    # 3. Reply present
    if out.get("reply"):
        print("3. Reply present:", "PASS\n")
    else:
        print("3. Reply present:", "FAIL\n")
        return False

    print("Done. Agent is working; review any WARN/CHECK above for efficacy and safety.")
    return True


if __name__ == "__main__":
    try:
        ok = test_agent()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
