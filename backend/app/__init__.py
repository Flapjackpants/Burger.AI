from flask import Flask
from flask_cors import CORS
from .routes import api

def create_app():
    app = Flask(__name__)

    # enable CORS
    CORS(app)

    # register routes
    app.register_blueprint(api)

    return app