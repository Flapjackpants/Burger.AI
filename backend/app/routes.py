from flask import Response, stream_with_context, request, Blueprint, jsonify
import time
import json
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

@api.route('/stream', methods=['POST'])
def stream():
    try:
        result = composeData(request)

        data = request.json()
        if not data:
            return Response("data: error: No JSON body received\n\n", mimetype='text/event-stream'), 400

        def event_stream():
            try:
                for char in behavior:
                    yield f"data: {json.dumps(char)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(
            stream_with_context(event_stream()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            }
        )

    except Exception as e:
        return Response(
            f"data: {json.dumps({'error': str(e)})}\n\n",
            mimetype='text/event-stream',
            status=500
        )