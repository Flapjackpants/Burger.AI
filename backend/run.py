from app import create_app
from dotenv import load_dotenv
import os

# Load the .env file from the root directory (one level up)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
print("[Run] load_dotenv %s" % env_path)
load_dotenv(env_path)

print("[Run] create_app")
app = create_app()

if __name__ == "__main__":
    print("[Run] starting Flask on port 5001")
    app.run(port=5001, debug=True)