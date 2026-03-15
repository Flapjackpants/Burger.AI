import os
import sys
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# Get API key from environment
API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not API_KEY:
    print("Error: ANTHROPIC_API_KEY not found in environment variables.")
    sys.exit(1)

def list_models():
    print("Initializing Anthropic client...")
    client = Anthropic(api_key=API_KEY)
    
    try:
        print("Attempting to list models...")
        models = client.models.list()
        print("Available models:")
        for m in models.data:
            print(f"- {m.id}")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
