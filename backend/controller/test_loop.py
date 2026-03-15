"""
Test loop: iterate composeData in portions, run wrapper (agent) -> evaluator per case,
yield JSON payloads for streaming to the client.

Proposed JSON format for client visualization:

  Ready (first event):
    { "type": "ready", "message": "Connection established. Starting evaluation." }

  Portion (each batch of evaluated cases):
    {
      "type": "portion",
      "portion_index": 0,
      "category": "Sycophancy Check",
      "results": [
        {
          "prompt": "user prompt string",
          "agent_reply": "agent response text",
          "tool_calls": [ { "tool_name": "...", "arguments": {...}, "result": {...} } ],
          "evaluation": { "passed": true|false, "reason": "...", "score": 0-10 },
          "expected_behavior": "optional from red-team case"
        }
      ]
    }

  Done (final event):
    { "type": "done" }
"""
import json
from serverLLM.evaluatorLLM import evaluate


def _prompt_from_case(case):
    """Extract prompt string from a test case (dict with 'prompt' or raw string)."""
    if isinstance(case, dict):
        return case.get("prompt") or str(case)
    return str(case)


def _expected_behavior_from_case(case):
    """Extract expected_behavior from red-team case if present."""
    if isinstance(case, dict):
        return case.get("expected_behavior")
    return None


def run_evaluation_stream(compose_data, llm_config, wrapper_fn, portion_by_category=True):
    """
    Iterate composeData in portions; for each test case call wrapper_fn(prompt) -> (reply, tool_calls_log),
    then evaluate; collect results and yield a JSON-serializable dict per portion.

    Args:
        compose_data: dict from composeData(), { category: [cases] }
        llm_config: dict for evaluator (and optionally wrapper)
        wrapper_fn: callable(prompt: str) -> dict with "reply" and "tool_calls_log"
        portion_by_category: if True, one portion = one category; else use fixed size chunks

    Yields:
        dict: ready, portion, or done payload (see module docstring).
    """
    print("[TestLoop] run_evaluation_stream entered, categories=%s" % list(compose_data.keys()))
    yield {"type": "ready", "message": "Connection established. Starting evaluation."}
    print("[TestLoop] yielded ready")

    portion_index = 0
    for category, cases in compose_data.items():
        if not cases:
            print("[TestLoop] skip empty category: %s" % category)
            continue
        print("[TestLoop] processing category=%s, cases=%d" % (category, len(cases)))
        results = []
        for i, case in enumerate(cases):
            prompt = _prompt_from_case(case)
            if not prompt:
                print("[TestLoop] case %d: empty prompt, skip" % i)
                continue
            expected_behavior = _expected_behavior_from_case(case)
            print("[TestLoop] case %d: calling wrapper (prompt len=%d)" % (i, len(prompt)))
            try:
                out = wrapper_fn(prompt)
                reply = out.get("reply") or ""
                tool_calls_log = out.get("tool_calls_log") or []
            except Exception as e:
                print("[TestLoop] case %d: wrapper error: %s" % (i, e))
                reply = ""
                tool_calls_log = []
                results.append({
                    "prompt": prompt,
                    "agent_reply": "",
                    "tool_calls": [],
                    "evaluation": {"passed": False, "reason": f"Wrapper error: {e}", "score": 0},
                    "expected_behavior": expected_behavior,
                })
                continue
            print("[TestLoop] case %d: calling evaluator" % i)
            try:
                eval_result = evaluate(
                    category=category,
                    prompt=prompt,
                    response=reply,
                    tool_calls=tool_calls_log,
                    llm_config=llm_config,
                )
                evaluation = eval_result.get("evaluation") or {}
                print("[TestLoop] case %d: evaluated passed=%s score=%s" % (i, evaluation.get("passed"), evaluation.get("score")))
            except Exception as e:
                print("[TestLoop] case %d: evaluator error: %s" % (i, e))
                evaluation = {"passed": False, "reason": f"Evaluator error: {e}", "score": 0}
            results.append({
                "prompt": prompt,
                "agent_reply": reply,
                "tool_calls": tool_calls_log,
                "evaluation": {
                    "passed": evaluation.get("passed", False),
                    "reason": evaluation.get("reason", ""),
                    "score": evaluation.get("score", 0),
                },
                "expected_behavior": expected_behavior,
            })
        print("[TestLoop] yielding portion index=%d category=%s results=%d" % (portion_index, category, len(results)))
        yield {
            "type": "portion",
            "portion_index": portion_index,
            "category": category,
            "results": results,
        }
        portion_index += 1

    print("[TestLoop] yielding done")
    yield {"type": "done"}
