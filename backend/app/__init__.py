from flask import Flask
from flask_cors import CORS
from .routes import api
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from serverLLM.redTeamLLM import red_team_api
from serverLLM.evaluatorLLM import evaluator_api

def create_app():
    app = Flask(__name__)

    # enable CORS
    CORS(app)

    # register routes
    app.register_blueprint(api)
    app.register_blueprint(red_team_api, url_prefix="/red-team")
    app.register_blueprint(evaluator_api, url_prefix="/evaluator")

    return app