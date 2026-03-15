"""
Pipeline: composeData combines RedTeamLLM-generated test cases with generic test data.
Used by GET /composed-tests and POST /stream to serve combined red-team + generic tests per category.
Red-team generation runs in parallel across categories; a barrier ensures all finish before merging.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from serverLLM.redTeamLLM import generate_test_cases, get_categories
from serverLLM.generic_test_cases import get_generic_tests


def _generate_one_category(key, num_cases, llm_config):
    """Generate red-team cases for a single category. Used by the executor."""
    print("[Pipeline] generating red-team cases for category: %s" % key)
    result = generate_test_cases(key, num_cases=num_cases, llm_config=llm_config)
    cases = result["test_cases"]
    print("[Pipeline] red-team %s -> %d cases" % (key, len(cases)))
    return key, cases


def composeData(request=None):
    """Combine RedTeamLLM output with generic test data per category.

    For each category (Sycophancy Check, Prompt Injection Leak, etc.):
      - Fetches LLM-generated red-team test cases in parallel (one thread per category).
      - Barrier: waits until all categories have finished.
      - Fetches generic test cases (fixed list of prompts per category).
      - Returns one merged list per category: red_team_cases + generic_cases.

    Args:
        request: Flask request or None. If provided, request.json may contain:
            - llm_config (dict): Optional config passed to RedTeamLLM (personality, description, etc.).
            - num_cases (int): Optional number of red-team cases per category (default 5).

    Returns:
        dict: { category_name: [test_case, ...], ... }
              Each test_case is either a dict (from RedTeam) or a string (from generic).
    """
    print("[Pipeline] composeData entered, request=%s" % ("present" if request else "None"))
    data = (request.json or {}) if request else {}
    llm_config = data.get("llm_config") or {}
    if not llm_config and data:
        # Client may send flat keys (behavior, description, ...); map to llm_config
        llm_config = {
            "personality_statement": data.get("behavior"),
            "description": data.get("description"),
            "system_prompts": data.get("system_prompts"),
            "disallowed_topics": data.get("disallowed_topics"),
            "llm_link": data.get("llm_link"),
        }
        llm_config = {k: v for k, v in llm_config.items() if v is not None}
    num_cases = data.get("num_cases", 5)
    print("[Pipeline] composeData num_cases=%s, llm_config keys=%s" % (num_cases, list(llm_config.keys())))

    categories = get_categories()["categories"]
    print("[Pipeline] get_categories -> %d categories (parallel generation)" % len(categories))

    red_team_cases = {}
    max_workers = min(len(categories) + 1, 8)  # +1 so generic_tests can run alongside
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_generic = executor.submit(get_generic_tests, None, llm_config)
        futures_red = {
            executor.submit(_generate_one_category, key, num_cases, llm_config): key
            for key in categories
        }
        for future in as_completed(futures_red):
            try:
                key, cases = future.result()
                red_team_cases[key] = cases
            except Exception as e:
                key = futures_red[future]
                print("[Pipeline] red-team %s failed: %s" % (key, e))
                red_team_cases[key] = []

        print("[Pipeline] barrier done: all %d categories generated" % len(red_team_cases))
        generic_test_cases = future_generic.result()
    for k, v in generic_test_cases.items():
        print("[Pipeline] generic %s -> %d cases" % (k, len(v)))

    combined = {
        key: red_team_cases.get(key, []) + generic_test_cases.get(key, [])
        for key in set(red_team_cases) | set(generic_test_cases)
    }
    print("[Pipeline] composeData returning %d categories, total cases: %s" % (len(combined), {k: len(v) for k, v in combined.items()}))
    return combined
