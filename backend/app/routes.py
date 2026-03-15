from flask import Response, stream_with_context, request, Blueprint, jsonify
import json
import requests
from controller.pipeline import composeData
from controller.test_loop import run_evaluation_stream

api = Blueprint("api", __name__)

# Default agent URL when llm_link is not provided (agent /prompt endpoint)
DEFAULT_LLM_LINK = "http://127.0.0.1:5002"


def _get_wrapper(llm_config):
    """Return a callable(prompt) -> { reply, tool_calls_log } that POSTs to llm_link/prompt."""
    base = (llm_config or {}).get("llm_link") or DEFAULT_LLM_LINK
    base = base.rstrip("/")
    url = base + "/prompt" if not base.endswith("/prompt") else base
    print("[Routes] _get_wrapper: agent URL=%s" % url)

    def wrapper(prompt):
        print("[Routes] wrapper: POST to agent (prompt len=%d)" % len(prompt))
        try:
            r = requests.post(
                url,
                json={"message": prompt},
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            r.raise_for_status()
            out = r.json()
            reply = out.get("reply", "")
            tool_calls_log = out.get("tool_calls_log", [])
            print("[Routes] wrapper: agent returned reply (len=%d), tool_calls=%d" % (len(reply), len(tool_calls_log)))
            return {"reply": reply, "tool_calls_log": tool_calls_log}
        except requests.RequestException as e:
            print("[Routes] wrapper: request failed: %s" % e)
            raise
        except (ValueError, KeyError) as e:
            print("[Routes] wrapper: bad response: %s" % e)
            raise

    print("[Routes] _get_wrapper: wrapper ready")
    return wrapper


@api.route("/", methods=["GET"])
def home():
    print("[Routes] GET /")
    return jsonify({"message": "Flask backend running"})


@api.route("/data", methods=["POST"])
def receive_data():
    data = request.json
    print("[Routes] POST /data received keys:", list(data.keys()) if isinstance(data, dict) else "non-dict")
    return jsonify({"status": "success", "received": data})


@api.route("/stream", methods=["POST"])
def stream():
    print("[Routes] POST /stream entered")
    try:
        data = request.get_json() or {}
        print("[Routes] /stream request body keys:", list(data.keys()))
        llm_config = data.get("llm_config") or {}
        if not llm_config and data:
            llm_config = {
                "personality_statement": data.get("behavior"),
                "description": data.get("description"),
                "system_prompts": data.get("system_prompts"),
                "disallowed_topics": data.get("disallowed_topics"),
                "llm_link": data.get("llm_link"),
            }
            llm_config = {k: v for k, v in llm_config.items() if v is not None}
        print("[Routes] /stream llm_config keys:", list(llm_config.keys()))

        composed = composeData(request)
        print("[Routes] /stream composeData categories:", list(composed.keys()), "case counts:", {k: len(v) for k, v in composed.items()})
        wrapper_fn = _get_wrapper(llm_config)

        def event_stream():
            try:
                print("[Routes] event_stream: starting run_evaluation_stream")
                for payload in run_evaluation_stream(composed, llm_config, wrapper_fn):
                    ptype = payload.get("type", "?")
                    print("[Routes] event_stream: yielding payload type=%s" % ptype)
                    yield f"data: {json.dumps(payload)}\n\n"
                print("[Routes] event_stream: sending [DONE]")
                yield "data: [DONE]\n\n"
            except Exception as e:
                print("[Routes] event_stream: exception:", e)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        print("[Routes] /stream returning SSE Response")
        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        print("[Routes] /stream top-level exception:", e)
        return Response(
            f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n",
            mimetype="text/event-stream",
            status=500,
        )