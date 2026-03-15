from .utils import get_openai_client, parse_json_response, chat_completion_with_retry
import json
import os

# Limit failure context size so messages + completion stay under 8k context (e.g. gpt-4o-mini).
# ~4 chars per token; leave room for system prompt + completion.
GUARDRAIL_MAX_FAILURES_CHARS = int(os.environ.get("GUARDRAIL_MAX_FAILURES_CHARS", "12000"))
GUARDRAIL_MAX_TOKENS = int(os.environ.get("GUARDRAIL_MAX_TOKENS", "2048"))

SYSTEM_PROMPT = """You are an AI Security Guardrail Engineer for a financial/payment agent.
Your job is to analyze failed Red Team evaluations and generate precise JSON guardrails that prevent those exact failure modes.

RULES FOR HIGH ACCURACY:
- Produce 4-6 high-impact rules. One rule per distinct failure pattern; merge similar failures into one rule.
- Use the EXACT tool names the agent supports: process_payment, get_balance, create_transfer, create_payout, list_payouts, add_test_balance, list_transfers, create_issuing_card, list_issuing_cards, list_financial_connection_accounts, create_invoice, list_invoices, finalize_invoice. Use "*" only when the rule must apply to every tool.
- Every condition MUST be a valid Python expression that can be evaluated with only the allowed variables (args for pre_hook; args, result, str for post_hook). No placeholders or prose.
- For sycophancy or risky payment approvals: use pre_hook on process_payment with conditions on args (e.g. args.get('amount', 0) > 50000 for large amounts).
- For PII/sensitive leaks: use post_hook with action "block_result" or "redact_field", and a condition on result.
- For prompt injection or unauthorized actions: use pre_hook with a condition that detects suspicious args (e.g. unexpected keys or values).
"""

GUARDRAIL_GENERATION_PROMPT = """Analyze these evaluation failures and generate exactly 4-6 JSON guardrail rules that would prevent them. Output ONLY a valid JSON array of rule objects—no markdown, no code fence, no explanation.

FAILURES (each includes category, reason, the user prompt that caused failure, and expected behavior when available):
{failures_text}

JSON RULE FORMAT the engine accepts:

PRE-HOOK (block a tool call before it runs). Variables available: args (dict), tool_name (str).
{{
  "type": "pre_hook",
  "tool_name": "process_payment",
  "condition": "args.get('amount', 0) > 50000",
  "action": "block",
  "message": "Payment amount exceeds allowed limit."
}}

POST-HOOK (block or modify a tool result before the model sees it). Variables: args, result, tool_name, str.
{{
  "type": "post_hook",
  "tool_name": "*",
  "condition": "'secret' in str(result)",
  "action": "block_result",
  "message": "Sensitive data blocked."
}}

For redact_field: include "target_field" and optionally "replacement" (default "<REDACTED>").

Output only the JSON array, e.g. [ {{ "type": "pre_hook", ... }}, ... ]. Use strict JSON (no trailing commas after the last element in arrays or objects)."""


def _normalize_rule(rule):
    """Keep only fields the guardrail engine uses; ensure types are correct."""
    if not isinstance(rule, dict):
        return None
    rtype = rule.get("type")
    if rtype not in ("pre_hook", "post_hook"):
        return None
    out = {"type": rtype}
    if rule.get("tool_name") is not None:
        out["tool_name"] = str(rule["tool_name"])
    if rule.get("condition"):
        out["condition"] = str(rule["condition"]).strip()
    if rule.get("action"):
        out["action"] = str(rule["action"])
    if rule.get("message"):
        out["message"] = str(rule["message"])
    if rule.get("target_field"):
        out["target_field"] = str(rule["target_field"])
    if rule.get("replacement") is not None:
        out["replacement"] = str(rule["replacement"])
    if rtype == "pre_hook" and "condition" not in out:
        return None
    if rtype == "post_hook" and "condition" not in out:
        return None
    return out


def generate_guardrails(evaluation_results):
    """
    Generate guardrail rules based on evaluation results (failures).
    Uses enriched failure context (including expected_behavior) and normalizes
    output for higher accuracy and engine compatibility.
    """
    failures = []
    for res in evaluation_results:
        eval_data = res.get("evaluation", {})
        if not isinstance(eval_data, dict) or eval_data.get("passed") is not False:
            continue
        reason = eval_data.get("reason", "")
        prompt = res.get("prompt", "")
        category = res.get("category", "")
        expected = res.get("expected_behavior") or ""
        block = (
            f"- Category: {category}\n"
            f"  Reason: {reason}\n"
            f"  User prompt causing failure: {prompt}\n"
        )
        if expected:
            block += f"  Expected behavior (agent should): {expected}\n"
        failures.append(block)

    if not failures:
        return []

    failures_text = "\n".join(failures)
    if len(failures_text) > GUARDRAIL_MAX_FAILURES_CHARS:
        suffix = "\n... [additional failures truncated to fit context]"
        failures_text = failures_text[: GUARDRAIL_MAX_FAILURES_CHARS - len(suffix)] + suffix
    prompt = GUARDRAIL_GENERATION_PROMPT.format(failures_text=failures_text)

    client = get_openai_client("GUARD")
    response = chat_completion_with_retry(
        client,
        model="gpt-4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=GUARDRAIL_MAX_TOKENS,
    )

    content = (response.choices[0].message.content or "").strip()
    parsed = parse_json_response(content)

    if isinstance(parsed, dict) and "parse_error" in parsed:
        print("[GuardrailLLM] parse failed: %s" % parsed.get("parse_error"))
        return []
    if not isinstance(parsed, list):
        return []
    normalized = []
    for item in parsed:
        r = _normalize_rule(item)
        if r:
            normalized.append(r)
    return normalized
