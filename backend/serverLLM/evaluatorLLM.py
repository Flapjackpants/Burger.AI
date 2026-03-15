from .utils import get_openai_client, parse_json_response, chat_completion_with_retry
from .prompts import EVALUATION_PROMPTS
import json
import os
import threading
import time
from datetime import datetime, timezone

# Min seconds between evaluator API calls. Lower = more throughput, higher 429 risk (retries handle it).
# Set to 0 to disable throttling and rely on 429 retries only. Default 2.0 balances speed vs rate limits.
EVALUATOR_MIN_INTERVAL_SECONDS = max(0.0, float(os.environ.get("EVALUATOR_MIN_INTERVAL_SECONDS", "0.0")))
# Truncate long inputs to control token usage (chars ≈ tokens for English).
EVALUATOR_MAX_PROMPT_CHARS = int(os.environ.get("EVALUATOR_MAX_PROMPT_CHARS", "2500"))
EVALUATOR_MAX_RESPONSE_CHARS = int(os.environ.get("EVALUATOR_MAX_RESPONSE_CHARS", "3000"))
EVALUATOR_MAX_TOOL_CALLS_CHARS = int(os.environ.get("EVALUATOR_MAX_TOOL_CALLS_CHARS", "1500"))
_evaluator_lock = threading.Lock()
_last_evaluator_call_time = 0.0


def _truncate(s, max_chars, suffix=" [truncated]"):
    if not s or len(s) <= max_chars:
        return s or ""
    return s[: max_chars - len(suffix)] + suffix


def format_llm_config(llm_config):
    """Format LLM configuration for inclusion in the evaluator prompt."""
    print("[Evaluator] format_llm_config, keys=%s" % (list(llm_config.keys()) if llm_config else "None"))
    if not llm_config:
        return "No specific LLM configuration provided."
    
    config_str = "LLM Configuration:\n"
    if "personality_statement" in llm_config:
        config_str += f"- Personality: {llm_config['personality_statement']}\n"
    if "description" in llm_config:
        config_str += f"- Description: {llm_config['description']}\n"
    if "system_prompts" in llm_config and llm_config["system_prompts"]:
        config_str += f"- System Prompts: {', '.join(llm_config['system_prompts'])}\n"
    if "disallowed_topics" in llm_config and llm_config["disallowed_topics"]:
        config_str += f"- Disallowed Topics: {', '.join(llm_config['disallowed_topics'])}\n"
    
    return config_str

def _is_guardrail_block_result(result):
    """True if result is a guardrail block error (tool was blocked by security guardrail)."""
    if not isinstance(result, dict):
        return False
    err = result.get("error")
    if not isinstance(err, str):
        return False
    err_lower = err.lower()
    return "blocked" in err_lower and "guardrail" in err_lower


def format_tool_calls(tool_calls):
    """Format tool calls for inclusion in the evaluator prompt (truncated to limit tokens)."""
    print("[Evaluator] format_tool_calls, count=%d" % (len(tool_calls) if tool_calls else 0))
    if not tool_calls:
        return "No tool calls made by the agent."
    
    calls_str = "Tool Calls Made by the Agent:\n"
    for i, call in enumerate(tool_calls, 1):
        result = call.get("result", "No result")
        result_line = f"   Result: {result}"
        if _is_guardrail_block_result(result):
            result_line += " [GUARDRAIL BLOCKED - treat as successful refusal]"
        result_line += "\n"
        calls_str += f"{i}. Tool: {call.get('tool_name', 'Unknown')}\n"
        calls_str += f"   Arguments: {call.get('arguments', {})}\n"
        calls_str += result_line
    return _truncate(calls_str, EVALUATOR_MAX_TOOL_CALLS_CHARS)

def evaluate(category, prompt, response, tool_calls=None, llm_config=None):
    """
    Evaluate an agentic AI response for a given category.
    
    Args:
        category (str): The evaluation category (e.g., "Sycophancy Check").
        prompt (str): The user prompt given to the agent.
        response (str): The agent's text response.
        tool_calls (list, optional): List of tool call records made by the agent.
        llm_config (dict, optional): LLM configuration details.
    
    Returns:
        dict: Evaluation result with category, evaluation details, and metadata.
    
    Raises:
        ValueError: If required parameters are missing or invalid.
    """
    print("[Evaluator] evaluate entered category=%s prompt_len=%d response_len=%d" % (category, len(prompt) if prompt else 0, len(response) if response else 0))
    if not category:
        raise ValueError("Category is required")
    
    if category not in EVALUATION_PROMPTS:
        raise ValueError(f"Invalid category. Available: {list(EVALUATION_PROMPTS.keys())}")
    
    if not prompt or not response:
        raise ValueError("Both 'prompt' and 'response' are required for evaluation.")
    
    tool_calls = tool_calls or []
    llm_config = llm_config or {}

    # Truncate to stay under token limits and reduce cost
    prompt_trimmed = _truncate(prompt, EVALUATOR_MAX_PROMPT_CHARS)
    response_trimmed = _truncate(response, EVALUATOR_MAX_RESPONSE_CHARS)
    llm_config_str = format_llm_config(llm_config)
    tool_calls_str = format_tool_calls(tool_calls)
    print("[Evaluator] calling OpenAI for evaluation (category=%s)" % category)
    system_instruction = EVALUATION_PROMPTS[category].format(
        prompt=prompt_trimmed,
        response=response_trimmed,
        tool_calls_str=tool_calls_str,
        llm_config_str=llm_config_str
    )

    openai_client = get_openai_client("EVAL")
    model = os.environ.get("EVALUATOR_LLM_MODEL", "gpt-4o-mini")

    # Serialize and optionally throttle evaluator calls (0 = no throttle, rely on 429 retries)
    global _last_evaluator_call_time
    with _evaluator_lock:
        now = time.monotonic()
        if EVALUATOR_MIN_INTERVAL_SECONDS > 0 and _last_evaluator_call_time > 0:
            elapsed = now - _last_evaluator_call_time
            if elapsed < EVALUATOR_MIN_INTERVAL_SECONDS:
                sleep_time = EVALUATOR_MIN_INTERVAL_SECONDS - elapsed
                print("[Evaluator] throttle: sleeping %.1fs before next call" % sleep_time)
                time.sleep(sleep_time)
        completion = chat_completion_with_retry(
            openai_client,
            model=model,
            messages=[
                {"role": "system", "content": "You are an automated AI evaluation system. Output valid JSON only."},
                {"role": "user", "content": system_instruction}
            ],
            temperature=0.0,
            max_tokens=400,
        )
        _last_evaluator_call_time = time.monotonic()

    eval_content = completion.choices[0].message.content.strip()
    print("[Evaluator] OpenAI response received, content len=%d" % len(eval_content))

    # Parse JSON using robust utility
    evaluation_result = parse_json_response(eval_content)
    print("[Evaluator] parse_json_response -> passed=%s" % evaluation_result.get("passed") if isinstance(evaluation_result, dict) else "n/a")
    
    # If parsing failed and returned the raw dict, structure it as a failure
    if "parse_error" in evaluation_result:
        evaluation_result = {
            "passed": False,
            "reason": f"Failed to parse evaluator response: {evaluation_result['parse_error']}",
            "score": 0,
            "raw_response": eval_content
        }

    print("[Evaluator] evaluate returning category=%s" % category)
    return {
        "category": category,
        "evaluation": evaluation_result,
        "metadata": {
            "model": model,
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }
    }
