from flask import Flask
from flask_cors import CORS
from .routes import api
from serverLLM.redTeamLLM_api import red_team_api
from serverLLM.evaluatorLLM import evaluator_api
from companyLLM.toy_model import company_api

def create_app():
    app = Flask(__name__)

    # enable CORS
    CORS(app)

    # register routes
    app.register_blueprint(api)
    app.register_blueprint(red_team_api, url_prefix="/red-team")
    app.register_blueprint(evaluator_api, url_prefix="/evaluator")
    app.register_blueprint(company_api, url_prefix="/company")

    return app