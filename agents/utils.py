"""OpenAI client and helpers. Self-contained for agents."""
import json
import os
from openai import OpenAI

_client = None

# Load agents/.env as soon as this module is imported so OPENAI_API_KEY is available
def _load_env():
    agents_dir = os.path.abspath(os.path.dirname(__file__))
    env_path = os.path.join(agents_dir, ".env")
    # Try python-dotenv first
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except Exception:
        pass
    # Fallback: read .env manually so key works even without dotenv or if path was wrong
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    k, v = key.strip(), value.strip()
                    if k == "OPENAI_API_KEY" and v:
                        os.environ["OPENAI_API_KEY"] = v
                    elif k == "STRIPE_SECRET_KEY" and v:
                        os.environ["STRIPE_SECRET_KEY"] = v


_load_env()


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Add it to agents/.env as one line: OPENAI_API_KEY=sk-your-key"
            )
        client = OpenAI(api_key=api_key)
        _client = client
    return _client


def parse_json_response(content: str):
    """Parse JSON from LLM response; handles markdown code blocks and extra text."""
    try:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        start_idx = 0
        end_idx = len(content)
        if not (content.startswith("{") or content.startswith("[")):
            first_brace, first_bracket = content.find("{"), content.find("[")
            if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                start_idx = first_brace
            elif first_bracket != -1:
                start_idx = first_bracket
        if not (content.endswith("}") or content.endswith("]")):
            last_brace, last_bracket = content.rfind("}"), content.rfind("]")
            if last_brace != -1 and (last_bracket == -1 or last_brace > last_bracket):
                end_idx = last_brace + 1
            elif last_bracket != -1:
                end_idx = last_bracket + 1
        return json.loads(content[start_idx:end_idx])
    except json.JSONDecodeError as e:
        return {"parse_error": str(e), "raw_content": content}
