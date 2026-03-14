from flask import Flask
from flask_cors import CORS
from .routes import api
from companyLLM.toy_model import company_api

def create_app():
    app = Flask(__name__)

    # enable CORS
    CORS(app)

    # register routes
    app.register_blueprint(api)
    app.register_blueprint(company_api, url_prefix="/company")

    return app