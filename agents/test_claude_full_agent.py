import os
import sys
import json
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Ensure we can import from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.tools import TOOLS, run_tool
from backend.serverLLM.guardrail_engine import GuardrailEngine
from anthropic import Anthropic

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '.env')) # agents/.env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', '.env')) # backend/.env

# Configuration
CLAUDE_MODEL = "claude-sonnet-4-6"

class ClaudePaymentAgent:
    """
    A version of the PaymentAgent that uses Anthropic's Claude instead of OpenAI.
    Demonstrates that the GuardrailEngine works cross-model.
    """
    def __init__(self, model: str = CLAUDE_MODEL):
        self.model = model
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        self.client = Anthropic(api_key=api_key)
        self.tool_calls_log: List[Any] = []

    def _convert_tools_to_anthropic(self, openai_tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI function definitions to Anthropic tool definitions."""
        anthropic_tools = []
        for tool in openai_tools:
            if tool.get("type") != "function":
                continue
            
            func = tool.get("function", {})
            anthropic_tools.append({
                "name": func.get("name"),
                "description": func.get("description"),
                "input_schema": func.get("parameters")
            })
        return anthropic_tools

    def run(self, user_id: str, user_message: str, dynamic_guardrails: List[Dict] = None):
        print(f"--- Running Claude Agent ({self.model}) for user: {user_id} ---")
        
        # Initialize Guardrail Engine
        engine = GuardrailEngine(dynamic_guardrails or [])
        
        # Prepare Tools
        claude_tools = self._convert_tools_to_anthropic(TOOLS)
        
        # Conversation History
        # Note: Claude system prompt is a top-level parameter, not a message
        messages = [
            {"role": "user", "content": f"[user_id: {user_id}] {user_message}"}
        ]
        
        system_prompt = """You are a Stripe-powered payment assistant. 
        Use the provided tools to answer user questions. 
        Always reply with a text summary after using a tool."""

        # Loop for tool use
        max_turns = 5
        final_reply = ""

        for i in range(max_turns):
            print(f"Turn {i+1}...")
            
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    tools=claude_tools,
                    system=system_prompt,
                    messages=messages
                )
            except Exception as e:
                print(f"Error calling Claude: {e}")
                return {"reply": f"Error: {str(e)}", "log": self.tool_calls_log}

            # Check if text content exists and print it
            for content in response.content:
                if content.type == 'text':
                    print(f"Claude: {content.text}")
                    final_reply = content.text

            # Check for tool use
            if response.stop_reason != "tool_use":
                # Final response reached
                break

            # Add assistant's response to history
            # Convert ContentBlocks to dictionaries for the next API call
            assistant_content_blocks = []
            for block in response.content:
                if block.type == "text":
                    assistant_content_blocks.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content_blocks.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            
            messages.append({"role": "assistant", "content": assistant_content_blocks})

            # Process tool calls
            tool_results = []
            
            for block in response.content:
                if block.type == 'tool_use':
                    tool_name = block.name
                    tool_args = block.input
                    tool_id = block.id
                    
                    print(f"Tool Request: {tool_name}({tool_args})")

                    # --- GUARDRAIL CHECK (PRE-HOOK) ---
                    is_blocked, block_reason = engine.check_pre_hook(tool_name, tool_args)
                    
                    if is_blocked:
                        print(f"🚫 GUARDRAIL BLOCKED: {block_reason}")
                        result_content = {"error": block_reason}
                        # Log it
                        self.tool_calls_log.append({
                            "tool": tool_name, 
                            "args": tool_args, 
                            "result": result_content, 
                            "blocked": True
                        })
                    else:
                        # User-defined tool execution (Execute the Python function)
                        # We need to find the function mapping, simplistic approach for now:
                        try:
                            # In real agent, we map name -> function. 
                            # Here we use the run_tool helper from agents.tools
                            raw_result = run_tool(tool_name, tool_args)
                            
                            # --- GUARDRAIL CHECK (POST-HOOK) ---
                            final_result = engine.apply_post_hooks(tool_name, tool_args, raw_result)
                            
                            result_content = final_result
                             # Log it
                            self.tool_calls_log.append({
                                "tool": tool_name, 
                                "args": tool_args, 
                                "result": final_result, 
                                "blocked": False
                            })
                            print(f"✅ Tool Executed. Result: {str(result_content)[:100]}...")

                        except Exception as e:
                            result_content = {"error": str(e)}
                            print(f"❌ Tool Execution Failed: {e}")

                    # append result to message history for Claude
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result_content)
                    })

            # Append tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        return {"reply": final_reply, "log": self.tool_calls_log}


def test_claude_agent():
    print("\n\n=== TEST 1: Safe Request ===")
    agent = ClaudePaymentAgent()
    # No guardrails, simple balance check
    agent.run("test_user", "What is my balance?")

    print("\n\n=== TEST 2: Guardrail Violation ===")
    # Define a guardrail
    rules = [{
        "tool_name": "process_payment",
        "condition": "args.get('amount', 0) > 500",
        "message": "Payment too high! Max $500.",
        "type": "pre_hook"
    }]
    
    # Try to violate it (pay $1000)
    # Note: amount in tool 'process_payment' is usually in cents for Stripe, 
    # but the tool description says "amount in cents".
    # Let's assume the user asks for "10 dollars" -> 1000 cents.
    # If our rule checks raw args: 1000 > 500.
    
    print("Injecting Guardrail: Block payments with amount > 500 (cents)")
    agent.run("test_user_2", "Please pay 10 dollars (1000 cents) for a burger.", dynamic_guardrails=rules)

if __name__ == "__main__":
    test_claude_agent()
