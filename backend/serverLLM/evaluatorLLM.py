from flask import Blueprint, request, jsonify
from .utils import get_openai_client, parse_json_response
from .prompts import EVALUATION_PROMPTS
import json

evaluator_api = Blueprint("evaluator_api", __name__)

def format_llm_config(llm_config):
    """Format LLM configuration for inclusion in the evaluator prompt."""
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

@evaluator_api.route("/evaluate", methods=["POST"])
def evaluate():
    try:
        data = request.json
        category = data.get("category")
        prompt_text = data.get("prompt")
        response_text = data.get("response")
        llm_config = data.get("llm_config", {})

        if not category:
            return jsonify({"error": "Category is required"}), 400
        
        if category not in EVALUATION_PROMPTS:
            return jsonify({"error": f"Invalid category. Available: {list(EVALUATION_PROMPTS.keys())}"}), 400

        if not prompt_text or not response_text:
             return jsonify({"error": "Both 'prompt' and 'response' are required for evaluation."}), 400

        # Construct the evaluation prompt
        llm_config_str = format_llm_config(llm_config)
        system_instruction = EVALUATION_PROMPTS[category].format(
            prompt=prompt_text,
            response=response_text,
            llm_config_str=llm_config_str
        )

        openai_client = get_openai_client()
        
        # Call the Evaluator LLM (GPT-4 recommended for evaluation)
        completion = openai_client.chat.completions.create(
            model="gpt-4", 
            messages=[
                {"role": "system", "content": "You are an automated AI evaluation system. Output valid JSON only."},
                {"role": "user", "content": system_instruction}
            ],
            temperature=0.0 # Low temperature for consistent evaluation
        )

        eval_content = completion.choices[0].message.content.strip()

        # Parse JSON using robust utility
        evaluation_result = parse_json_response(eval_content)
        
        # If parsing failed and returned the raw dict, structure it as a failure
        if "parse_error" in evaluation_result:
             evaluation_result = {
                "passed": False,
                "reason": f"Failed to parse evaluator response: {evaluation_result['parse_error']}",
                "score": 0,
                "raw_response": eval_content
            }

        return jsonify({
            "category": category,
            "evaluation": evaluation_result,
            "metadata": {
                "model": "gpt-4",
                "evaluated_at": "timestamp_placeholder" # You can add actual timestamp
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
