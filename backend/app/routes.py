from flask import Blueprint, jsonify, request, Response
import time

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

@api.route('/stream')
def stream():
    def event_stream():
        while True:
            time.sleep(1)
            yield f"data: hello\n\n"
    
    return Response(event_stream(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })