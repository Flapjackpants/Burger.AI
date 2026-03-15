from .utils import get_openai_client, parse_json_response, chat_completion_with_retry
from .prompts import EVALUATION_PROMPTS
import json
from datetime import datetime, timezone

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

def format_tool_calls(tool_calls):
    """Format tool calls for inclusion in the evaluator prompt."""
    print("[Evaluator] format_tool_calls, count=%d" % (len(tool_calls) if tool_calls else 0))
    if not tool_calls:
        return "No tool calls made by the agent."
    
    calls_str = "Tool Calls Made by the Agent:\n"
    for i, call in enumerate(tool_calls, 1):
        calls_str += f"{i}. Tool: {call.get('tool_name', 'Unknown')}\n"
        calls_str += f"   Arguments: {call.get('arguments', {})}\n"
        calls_str += f"   Result: {call.get('result', 'No result')}\n"
    
    return calls_str

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

    # Construct the evaluation prompt
    llm_config_str = format_llm_config(llm_config)
    tool_calls_str = format_tool_calls(tool_calls)
    print("[Evaluator] calling OpenAI for evaluation (category=%s)" % category)
    system_instruction = EVALUATION_PROMPTS[category].format(
        prompt=prompt,
        response=response,
        tool_calls_str=tool_calls_str,
        llm_config_str=llm_config_str
    )

    openai_client = get_openai_client("EVAL")

    # Call the Evaluator LLM (GPT-4 recommended for evaluation); retries on 429
    completion = chat_completion_with_retry(
        openai_client,
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an automated AI evaluation system. Output valid JSON only."},
            {"role": "user", "content": system_instruction}
        ],
        temperature=0.0  # Low temperature for consistent evaluation
    )

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
            "model": "gpt-4",
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }
    }
