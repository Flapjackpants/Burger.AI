"""
Pipeline: composeData combines RedTeamLLM-generated test cases with generic test data.
Used by GET /composed-tests and POST /stream to serve combined red-team + generic tests per category.
"""
from serverLLM.redTeamLLM import generate_test_cases, get_categories
from serverLLM.generic_test_cases import get_generic_tests


def composeData(request=None):
    """Combine RedTeamLLM output with generic test data per category.

    For each category (Sycophancy Check, Prompt Injection Leak, etc.):
      - Fetches LLM-generated red-team test cases (objects with prompt, expected_behavior, test_reason).
      - Fetches generic test cases (fixed list of prompts for that category).
      - Returns one merged list per category: red_team_cases + generic_cases.

    Args:
        request: Flask request or None. If provided, request.json may contain:
            - llm_config (dict): Optional config passed to RedTeamLLM (personality, description, etc.).
            - num_cases (int): Optional number of red-team cases per category (default 5).

    Returns:
        dict: { category_name: [test_case, ...], ... }
              Each test_case is either a dict (from RedTeam) or a string (from generic).
    """
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

    categories = get_categories()["categories"]
    red_team_cases = {}
    for key in categories:
        red_team_cases[key] = generate_test_cases(
            key, num_cases=num_cases, llm_config=llm_config
        )["test_cases"]

    generic_test_cases = get_generic_tests(None, llm_config)

    combined = {
        key: red_team_cases.get(key, []) + generic_test_cases.get(key, [])
        for key in set(red_team_cases) | set(generic_test_cases)
    }
    return combined
