from flask import Blueprint, jsonify, request

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