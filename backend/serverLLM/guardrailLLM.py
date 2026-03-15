from .utils import get_openai_client, parse_json_response, chat_completion_with_retry
import json

SYSTEM_PROMPT = """You are an AI Security Guardrail Engineer.
Your job is to analyze failed Red Team evaluations and generate JSON-based guardrails to prevent those specific failures in the future.
The agent operates with tools like `process_payment`, `get_balance`, `create_transfer`, etc.
"""

GUARDRAIL_GENERATION_PROMPT = """
Based on the following evaluation failures, generate a list of implementation-agnostic JSON guardrails.

FAILURES:
{failures_text}

The agent has a guardrail engine that understands the following JSON structure:

1. PRE-HOOK (Blocks tool calls before they happen):
{{
    "type": "pre_hook",
    "tool_name": "process_payment", // or "*" for all
    "condition": "args['amount'] > 5000", // Python expression using 'args' dictionary
    "action": "block",
    "message": "Payment amount too high."
}}

2. POST-HOOK (Modifies/Blocks tool results before model sees them):
{{
    "type": "post_hook",
    "tool_name": "*",
    "condition": "'private_key' in str(result)", // Python expression using 'result' (dict or str)
    "action": "redact_field", // or "block_result"
    "target_field": "private_key", // For redact_field action
    "message": "Sensitive data blocked." // For block_result action
}}

Generate a valid JSON list of these rule objects.
"""

def generate_guardrails(evaluation_results):
    """
    Generate guardrail rules based on evaluation results (failures).
    
    Args:
        evaluation_results (list): List of evaluation dicts from EvaluatorLLM.
        
    Returns:
        list: A list of guardrail rule dictionaries.
    """
    # 1. format failures
    failures = []
    for res in evaluation_results:
        # Check if failed
        eval_data = res.get("evaluation", {})
        if isinstance(eval_data, dict) and eval_data.get("passed") is False:
            failures.append(f"- Category: {res.get('category')}\n  Reason: {eval_data.get('reason')}\n  Raw Prompt causing failure: {res.get('prompt')}")
            
    if not failures:
        return []

    failures_text = "\n".join(failures)
    
    prompt = GUARDRAIL_GENERATION_PROMPT.format(failures_text=failures_text)
    
    client = get_openai_client("GUARD")
    response = chat_completion_with_retry(
        client,
        model="gpt-4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )
    
    content = response.choices[0].message.content
    rules = parse_json_response(content)
    
    if isinstance(rules, list):
        return rules
    return []
