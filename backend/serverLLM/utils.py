from openai import OpenAI
import os
import json
import re
import time

# Sync client: redTeamLLM uses .create() without await
client = None

# Retry config for rate limits (429)
OPENAI_RETRY_MAX_ATTEMPTS = 5
OPENAI_RETRY_BASE_SECONDS = 2
OPENAI_RETRY_MAX_SECONDS = 60


def _is_rate_limit_error(e):
    """True if the exception is a 429 / rate limit error."""
    err_str = str(e).lower()
    if "429" in err_str or "rate_limit" in err_str or "rate limit" in err_str:
        return True
    return getattr(e, "status_code", None) == 429


def _parse_retry_after_ms(e):
    """Parse 'Please try again in Xms' from error message; return seconds or None."""
    m = re.search(r"try again in (\d+)ms", str(e), re.I)
    if m:
        return max(1, int(m.group(1)) / 1000.0)
    return None


def chat_completion_with_retry(client, **kwargs):
    """
    Call client.chat.completions.create(**kwargs) with retry on 429 rate limit.
    Uses retry-after from error message when present, else exponential backoff.
    """
    last_error = None
    for attempt in range(1, OPENAI_RETRY_MAX_ATTEMPTS + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            last_error = e
            if not _is_rate_limit_error(e) or attempt >= OPENAI_RETRY_MAX_ATTEMPTS:
                raise
            wait = _parse_retry_after_ms(e)
            if wait is None:
                wait = min(OPENAI_RETRY_MAX_SECONDS, OPENAI_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
            print("[Utils] Rate limit (429); retry %d/%d in %.1fs: %s" % (attempt, OPENAI_RETRY_MAX_ATTEMPTS, wait, str(e)[:120]))
            time.sleep(wait)
    raise last_error


def get_openai_client(llm_type):
    global client
    print("[Utils] get_openai_client")
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY_" + llm_type)
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

        def _try_parse(s):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return None

        out = _try_parse(cleaned_content)
        if out is not None:
            print("[Utils] parse_json_response OK (type=%s)" % type(out).__name__)
            return out

        # Repair common LLM JSON mistakes
        repaired = re.sub(r",\s*\]", "]", cleaned_content)
        repaired = re.sub(r",\s*}", "}", repaired)
        out = _try_parse(repaired)
        if out is not None:
            print("[Utils] parse_json_response OK after trailing-comma repair (type=%s)" % type(out).__name__)
            return out
        # Missing comma between array/object elements: } { or ] [
        repaired = re.sub(r"\}\s*\{", "},{", repaired)
        repaired = re.sub(r"\]\s*\[", "],[", repaired)
        out = _try_parse(repaired)
        if out is not None:
            print("[Utils] parse_json_response OK after comma repair (type=%s)" % type(out).__name__)
            return out

        raise json.JSONDecodeError("JSON repair failed", content, 0)

    except json.JSONDecodeError as e:
        # If parsing fails, return dict so callers can handle without crashing
        print("[Utils] parse_json_response JSONDecodeError: %s" % e)
        return {"parse_error": str(e), "raw_content": content}
