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


def _handle_prompt_response(data):
    """Parse request data and return (message, user_id, guardrails). Raises on invalid."""
    message = (data.get("message") or "").strip()
    if not message:
        return None, None, None
    user_id = (data.get("user_id") or "api_user").strip() or "api_user"
    guardrails = data.get("guardrails") or {}
    return message, user_id, guardrails


def _json_reply(out):
    return jsonify({"reply": out.get("reply", ""), "tool_calls_log": out.get("tool_calls_log", [])})


def _json_error(e):
    return jsonify({"reply": f"[Agent error] {str(e)}", "tool_calls_log": [], "error": str(e)})


@app.route("/prompt", methods=["POST"])
def prompt():
    """
    OpenAI payment agent. Send JSON: {"message": "...", "user_id": "optional", "guardrails": optional}.
    Returns: {"reply": "...", "tool_calls_log": [...]}. On failure returns 200 with error in body.
    """
    data = request.get_json() or {}
    message, user_id, guardrails = _handle_prompt_response(data)
    if message is None:
        return jsonify({"error": "message is required"}), 400
    try:
        run_payment_agent = _get_agent()
        out = run_payment_agent(user_id=user_id, user_message=message, guardrails=guardrails)
        return _json_reply(out)
    except Exception as e:
        traceback.print_exc()
        return _json_error(e)


@app.route("/claude", methods=["POST"])
def claude():
    """
    Claude agent. Same contract as /prompt: {"message": "...", "user_id": "optional", "guardrails": optional}.
    Returns: {"reply": "...", "tool_calls_log": [...]}. On failure returns 200 with error in body.
    """
    data = request.get_json() or {}
    message, user_id, guardrails = _handle_prompt_response(data)
    if message is None:
        return jsonify({"error": "message is required"}), 400
    try:
        from agents.claude_agent import run_claude_agent
        out = run_claude_agent(user_id=user_id, user_message=message, guardrails=guardrails)
        return _json_reply(out)
    except Exception as e:
        traceback.print_exc()
        return _json_error(e)


if __name__ == "__main__":
    port = int(os.environ.get("AGENT_PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)
