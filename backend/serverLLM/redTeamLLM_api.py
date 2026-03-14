from flask import Blueprint, request, jsonify
from . import redTeamLLM

red_team_api = Blueprint("red_team_api", __name__)


@red_team_api.route("/generate-test-cases", methods=["POST"])
def generate_test_cases_endpoint():
    """Flask endpoint wrapper around redTeamLLM.generate_test_cases."""
    data = request.json or {}
    category = data.get("category")
    num_cases = data.get("num_cases", 5)
    llm_config = data.get("llm_config", {})

    try:
        payload = redTeamLLM.generate_test_cases(category, num_cases=num_cases, llm_config=llm_config)
        return jsonify(payload)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@red_team_api.route("/categories", methods=["GET"])
def get_categories_endpoint():
    """Flask endpoint wrapper around redTeamLLM.get_categories."""
    return jsonify(redTeamLLM.get_categories())
