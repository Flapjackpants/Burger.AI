from flask import Response, stream_with_context, request, Blueprint, jsonify
import json
import time
from controller.pipeline import composeData
api = Blueprint("api", __name__)

@api.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Flask backend running"})


@api.route("/data", methods=["POST"])
def receive_data():
    data = request.json
    return jsonify({
        "status": "success",
        "received": data
    })

@api.route("/stream", methods=["POST"])
def stream():
    try:
        result = composeData(request)

        def event_stream():
            try:
                for category, cases in result.items():
                    yield f"data: {json.dumps({'category': category, 'cases': cases})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        return Response(
            f"data: {json.dumps({'error': str(e)})}\n\n",
            mimetype="text/event-stream",
            status=500,
        )