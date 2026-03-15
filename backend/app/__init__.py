from flask import Flask
from flask_cors import CORS
from .routes import api
from companyLLM.toy_model import company_api

def create_app():
    print("[App] create_app")
    app = Flask(__name__)

    # enable CORS
    CORS(app)
    print("[App] CORS enabled")

    # register routes
    app.register_blueprint(api)
    app.register_blueprint(company_api, url_prefix="/company")
    print("[App] blueprints registered: api, company_api")

    return app