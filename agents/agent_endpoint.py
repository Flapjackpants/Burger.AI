"""
Flask server that exposes the payment agent over HTTP.
Run from repo root:  python -m agents.agent_endpoint
Or:  python agents/agent_endpoint.py
Then POST to /prompt with {"message": "Charge me 25 dollars for lunch"} (optional: "user_id").
Requires Python 3.9.4+.
"""
import os
import sys
import traceback

if sys.version_info < (3, 9, 4):
    sys.exit("This project requires Python 3.9.4 or newer. Current: %s" % sys.version)

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask("agent_endpoint")
CORS(app)

# Import after path is set
def _get_agent():
    from agents.payment_agent import run_payment_agent
    return run_payment_agent


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "agent_endpoint"})


@app.route("/prompt", methods=["POST"])
def prompt():
    """
    Prompt the agent like in the terminal. Send JSON:
      {"message": "Charge me 25 dollars for lunch", "user_id": "optional", "model": "openai" (default) or "claude"}
    Returns: {"reply": "...", "tool_calls_log": [{"tool_name", "arguments", "result"}, ...]}
    On agent failure we return 200 with reply/error so the evaluator can score it instead of 500.
    """
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    user_id = (data.get("user_id") or "api_user").strip() or "api_user"
    guardrails = data.get("guardrails") or {}
    
    # Check for model selection (demo feature)
    model_provider = (data.get("model") or "openai").lower()
    
    try:
        if model_provider.startswith("claude"):
             print(f"[Endpoint] Switching to CLAUDE agent for user {user_id}")
             from agents.claude_agent import run_claude_agent
             out = run_claude_agent(user_id=user_id, user_message=message, guardrails=guardrails)
        else:
             run_payment_agent = _get_agent()
             out = run_payment_agent(user_id=user_id, user_message=message, guardrails=guardrails)
             
        return jsonify({
            "reply": out.get("reply", ""),
            "tool_calls_log": out.get("tool_calls_log", []),
        })
    except Exception as e:
        # Log full traceback so you can see the cause of 500s in the agent terminal
        traceback.print_exc()
        # Return 200 with error in body so backend/evaluator get a consistent response
        return jsonify({
            "reply": f"[Agent error] {str(e)}",
            "tool_calls_log": [],
            "error": str(e),
        })


if __name__ == "__main__":
    port = int(os.environ.get("AGENT_PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)
