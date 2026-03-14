import json
from serverLLM.redTeamLLM import generate_test_cases, get_categories
from serverLLM.generic_test_cases import get_generic_tests

def composeData(request: json):
    ''''''
    data = request.json or {}
    llm_config = data.get("llm_config", {})

    keys = get_categories()["categories"]
    redTeamCases = {}
    for key in keys:
        redTeamCases[key] = generate_test_cases(key, num_cases=5, llm_config=llm_config)["test_cases"]
        print('j')
    print(redTeamCases)
    print('hello')
    genericTestCases = get_generic_tests()

    combined = {
        key: redTeamCases.get(key, []) + genericTestCases.get(key, [])
        for key in set(redTeamCases) | set(genericTestCases)
    }
    return combined


