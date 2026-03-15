"""
Test loop: iterate composeData; for each prompt run wrapper (agent) -> evaluator,
then yield one stream event per result (per-prompt streaming).
Cases are run in parallel; results are streamed as each completes.

JSON format for client:

  Ready (first event):
    { "type": "ready", "message": "Connection established. Starting evaluation." }

  Result (one event per prompt, streamed as soon as that prompt is evaluated):
    {
      "type": "result",
      "category": "Sycophancy Check",
      "case_index": 0,
      "prompt": "user prompt string",
      "agent_reply": "agent response text",
      "tool_calls": [ { "tool_name": "...", "arguments": {...}, "result": {...} } ],
      "evaluation": { "passed": true|false, "reason": "...", "score": 0-10 },
      "expected_behavior": "optional from red-team case"
    }

  Done (final event):
    { "type": "done" }
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from serverLLM.evaluatorLLM import evaluate

# Max concurrent (wrapper + evaluate) tasks; lower to avoid OpenAI rate limits (429).
TEST_LOOP_MAX_WORKERS = 3


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


def _run_one_case(category, case_index, case, wrapper_fn, llm_config):
    """Run wrapper then evaluator for a single case. Returns a result dict or None if skipped."""
    prompt = _prompt_from_case(case)
    if not prompt:
        print("[TestLoop] case %s/%d: empty prompt, skip" % (category, case_index))
        return None
    expected_behavior = _expected_behavior_from_case(case)
    print("[TestLoop] case %s/%d: calling wrapper (prompt len=%d)" % (category, case_index, len(prompt)))
    try:
        out = wrapper_fn(prompt)
        reply = out.get("reply") or ""
        tool_calls_log = out.get("tool_calls_log") or []
    except Exception as e:
        print("[TestLoop] case %s/%d: wrapper error: %s" % (category, case_index, e))
        return {
            "type": "result",
            "category": category,
            "case_index": case_index,
            "prompt": prompt,
            "agent_reply": "",
            "tool_calls": [],
            "evaluation": {"passed": False, "reason": f"Wrapper error: {e}", "score": 0},
            "expected_behavior": expected_behavior,
        }
    print("[TestLoop] case %s/%d: calling evaluator" % (category, case_index))
    try:
        eval_result = evaluate(
            category=category,
            prompt=prompt,
            response=reply,
            tool_calls=tool_calls_log,
            llm_config=llm_config,
        )
        evaluation = eval_result.get("evaluation") or {}
        print("[TestLoop] case %s/%d: evaluated passed=%s score=%s" % (category, case_index, evaluation.get("passed"), evaluation.get("score")))
    except Exception as e:
        print("[TestLoop] case %s/%d: evaluator error: %s" % (category, case_index, e))
        evaluation = {"passed": False, "reason": f"Evaluator error: {e}", "score": 0}
    return {
        "type": "result",
        "category": category,
        "case_index": case_index,
        "prompt": prompt,
        "agent_reply": reply,
        "tool_calls": tool_calls_log,
        "evaluation": {
            "passed": evaluation.get("passed", False),
            "reason": evaluation.get("reason", ""),
            "score": evaluation.get("score", 0),
        },
        "expected_behavior": expected_behavior,
    }


def run_evaluation_stream(compose_data, llm_config, wrapper_fn, portion_by_category=True):
    """
    For each test case: call wrapper_fn(prompt), then evaluate; yield one stream event
    per prompt. Cases are run in parallel; results are yielded as each completes.

    Args:
        compose_data: dict from composeData(), { category: [cases] }
        llm_config: dict for evaluator (and optionally wrapper)
        wrapper_fn: callable(prompt: str) -> dict with "reply" and "tool_calls_log"

    Yields:
        dict: ready, then one "result" per case (completion order), then done.
    """
    print("[TestLoop] run_evaluation_stream entered, categories=%s" % list(compose_data.keys()))
    yield {"type": "ready", "message": "Connection established. Starting evaluation."}
    print("[TestLoop] yielded ready")

    # Flatten to (category, case_index, case) and skip empty categories
    tasks = []
    for category, cases in compose_data.items():
        if not cases:
            print("[TestLoop] skip empty category: %s" % category)
            continue
        print("[TestLoop] queueing category=%s, cases=%d" % (category, len(cases)))
        for i, case in enumerate(cases):
            tasks.append((category, i, case))

    if not tasks:
        print("[TestLoop] no cases, yielding done")
        yield {"type": "done"}
        return

    max_workers = min(len(tasks), TEST_LOOP_MAX_WORKERS)
    print("[TestLoop] running %d cases with %d workers" % (len(tasks), max_workers))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_one_case, cat, idx, c, wrapper_fn, llm_config): (cat, idx)
            for cat, idx, c in tasks
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    print("[TestLoop] yielding result category=%s case=%d" % (result["category"], result["case_index"]))
                    yield result
            except Exception as e:
                cat, idx = futures[future]
                print("[TestLoop] task %s/%d failed: %s" % (cat, idx, e))
                yield {
                    "type": "result",
                    "category": cat,
                    "case_index": idx,
                    "prompt": "",
                    "agent_reply": "",
                    "tool_calls": [],
                    "evaluation": {"passed": False, "reason": str(e), "score": 0},
                    "expected_behavior": None,
                }

    print("[TestLoop] yielding done")
    yield {"type": "done"}
