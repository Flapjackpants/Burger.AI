from openai import OpenAI
import os
import json

# Sync client: redTeamLLM uses .create() without await
client = None

def get_openai_client():
    global client
    print("[Utils] get_openai_client")
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[Utils] Warning: OPENAI_API_KEY not found in environment variables.")
        client = OpenAI(api_key=api_key) if api_key else OpenAI()
        print("[Utils] OpenAI client created (cached)")
    return client

def parse_json_response(content):
    """
    Robustly parse JSON from an LLM response string.
    Handles Markdown code blocks, surrounding whitespace, and potential raw objects.
    """
    print("[Utils] parse_json_response content_len=%d" % (len(content) if content else 0))
    try:
        content = content.strip()
        # Remove Markdown Code Blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:] # Some LLMs might use just ```
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        # Attempt to find the first [ or { and the last ] or } if there is garbage text
        # Simple heuristic:
        start_idx = 0
        end_idx = len(content)
        
        if not (content.startswith("{") or content.startswith("[")):
             # Try to find first occurence
             first_brace = content.find("{")
             first_bracket = content.find("[")
             
             if first_brace == -1 and first_bracket == -1:
                 # No JSON structure found
                 pass 
             elif first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
                 start_idx = first_brace
             else:
                 start_idx = first_bracket

        if not (content.endswith("}") or content.endswith("]")):
             last_brace = content.rfind("}")
             last_bracket = content.rfind("]")
             
             if last_brace == -1 and last_bracket == -1:
                 pass
             elif last_brace != -1 and (last_bracket == -1 or last_brace > last_bracket):
                 end_idx = last_brace + 1
             else:
                 end_idx = last_bracket + 1
        
        cleaned_content = content[start_idx:end_idx]
        out = json.loads(cleaned_content)
        print("[Utils] parse_json_response OK (type=%s)" % type(out).__name__)
        return out
        
    except json.JSONDecodeError as e:
        # If parsing fails, return None or raise so the caller knows
        # For this app, return a dict indicating failure so we don't crash and can debug
        print("[Utils] parse_json_response JSONDecodeError: %s" % e)
        return {"parse_error": str(e), "raw_content": content}
