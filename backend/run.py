from app import create_app
from dotenv import load_dotenv
import os

# Load the .env file from the root directory (one level up)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = create_app()

if __name__ == "__main__":
    app.run(port=5001, debug=True)