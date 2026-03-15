import os
import json
from anthropic import Anthropic
import sys
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# Add the parent directory to sys.path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.serverLLM.guardrail_engine import GuardrailEngine

# Get API key from environment
API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not API_KEY:
    print("Error: ANTHROPIC_API_KEY not found in environment variables.")
    sys.exit(1)

def test_claude_tool_interception():
    print("Initializing Anthropic client...")
    client = Anthropic(api_key=API_KEY)

    # 1. Define a tool for Claude
    tools = [
        {
            "name": "process_refund",
            "description": "Process a refund for a user.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "amount": {"type": "number", "description": "The amount to refund in USD"}
                },
                "required": ["user_id", "amount"]
            }
        }
    ]

    # 2. Define a Guardrail Rule aimed at this tool
    # Rule: Block refunds over $500
    rules = [
        {
            "tool_name": "process_refund",
            "condition": "args.get('amount', 0) > 500",
            "message": "Refund amount exceeds safety limit of $500.",
            "type": "pre_hook"
        }
    ]
    
    engine = GuardrailEngine(rules)
    print("Guardrail Engine initialized with rule: Block refunds > $500")

    # 3. Prompt Claude to trigger the tool with a value that violates the rule
    print("Prompting Claude 3.5 Sonnet to refund $1000 (should be blocked)...")
    
    # Try a list of models until one works - Updated for 2026 models based on listing
    
    candidates = [
        "claude-sonnet-4-6",      # Highest priority
        "claude-opus-4-6",
        "claude-sonnet-4-5-20250929",
        "claude-3-5-sonnet-20241022", # Fallback for legacy
    ]
    
    response = None
    for model_id in candidates:
        try:
            print(f"Trying model: {model_id}...")
            message = client.messages.create(
                model=model_id,
                max_tokens=1024,
                tools=tools,
                messages=[
                    {"role": "user", "content": "Please process a refund of $1000 for user 'user123'."}
                ]
            )
            response = message
            print(f"Success with {model_id}!")
            break
        except Exception as e:
            print(f"Failed with {model_id}: {e}")
            if "authentication_error" in str(e):
                print("Your API key is invalid.")
                return

    if not response:
        print("\n[WARNING] Could not get a LIVE response from any model (Check API Key/Permissions).")
        print("Falling back to MOCKED response to demonstrate Guardrail logic compatibility...")
        
        # MOCK FALLBACK
        class MockToolUseBlock:
            def __init__(self, name, input_data):
                self.type = 'tool_use'
                self.name = name
                self.input = input_data

        class MockMessage:
            def __init__(self, tool_name, tool_input):
                self.content = [MockToolUseBlock(tool_name, tool_input)]
        
        # Simulate Claude trying to refund $1000
        message = MockMessage("process_refund", {"user_id": "user123", "amount": 1000})
    else:
        # Use response instead of message for the next part
        message = response

    # 4. Intercept the tool use
    # Claude's response structure for tool use:
    # message.content is a list of blocks. Look for type='tool_use'.
    
    tool_use_block = next((block for block in message.content if block.type == 'tool_use'), None)
    
    if not tool_use_block:
        print("Model did not call the tool as expected.")
        print("Response content:", message.content)
        return

    tool_name = tool_use_block.name
    tool_args = tool_use_block.input
    
    print(f"Intercepted Tool Call: {tool_name} with args: {tool_args}")

    # 5. Run Guardrail Check
    is_blocked, reason = engine.check_pre_hook(tool_name, tool_args)

    if is_blocked:
        print(f"SUCCESS: Guardrail blocked the call! Reason: {reason}")
    else:
        print("FAILURE: Guardrail did not block the call.")

    # 6. Test a safe call (just purely logic check, without cost)
    print("\nTesting safe call logic locally...")
    safe_args = {"user_id": "user123", "amount": 100}
    is_blocked_safe, _ = engine.check_pre_hook("process_refund", safe_args)
    if not is_blocked_safe:
         print(f"SUCCESS: Guardrail allowed safe call: {safe_args}")
    else:
         print(f"FAILURE: Guardrail blocked safe call.")

if __name__ == "__main__":
    test_claude_tool_interception()
