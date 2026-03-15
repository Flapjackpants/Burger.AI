import os
import sys
import json
from typing import Any, Dict, List, Optional
from anthropic import Anthropic
from dotenv import load_dotenv

# Ensure we can import from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.tools import TOOLS, run_tool
from backend.serverLLM.guardrail_engine import GuardrailEngine

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
            # Fallback for when running via endpoint where env files might be loaded differently
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            
        if not api_key:
            print("WARNING: ANTHROPIC_API_KEY not found. Agent will fail.")
            
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

    def run(self, user_id: str, user_message: str, guardrails: Optional[Any] = None):
        print(f"--- Running Claude Agent ({self.model}) for user: {user_id} ---")
        
        # Prepare Guardrail Engine
        dynamic_rules = []
        if isinstance(guardrails, list):
            dynamic_rules = guardrails
        # Note: If guardrails is a dict (legacy config), we currently ignore simply because
        # the Claude agent is new and we want to push the dynamic rules.
        # But we could easily map it if needed.
        
        engine = GuardrailEngine(dynamic_rules)

        # Message-level guardrail: block before LLM if user message matches phrase rules
        blocked, block_msg = engine.check_message(user_message)
        if blocked:
            return {
                "reply": block_msg or "Request blocked by security guardrail.",
                "tool_calls_log": [],
            }
        
        # Prepare Tools
        claude_tools = self._convert_tools_to_anthropic(TOOLS)
        
        # Conversation History
        messages = [
            {"role": "user", "content": f"[user_id: {user_id}] {user_message}"}
        ]
        
        system_prompt = """You are a Stripe-powered payment assistant. 
        Use the provided tools to answer user questions. 
        Always reply with a text summary after using a tool."""

        # Loop for tool use
        max_turns = 5
        final_reply = ""
        self.tool_calls_log = [] # Reset log

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
                return {"reply": f"Error: {str(e)}", "tool_calls_log": self.tool_calls_log}

            # Check if text content exists and print it
            for content in response.content:
                if content.type == 'text':
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
                    
                    result_content = {}
                    
                    if is_blocked:
                        print(f"🚫 GUARDRAIL BLOCKED: {block_reason}")
                        result_content = {"error": block_reason}
                        # Log it
                        self.tool_calls_log.append({
                            "tool_name": tool_name, 
                            "arguments": tool_args, 
                            "result": result_content, 
                            "blocked": True
                        })
                    else:
                        try:
                            # Run actual tool
                            raw_result = run_tool(tool_name, tool_args)
                            
                            # --- GUARDRAIL CHECK (POST-HOOK) ---
                            final_result = engine.apply_post_hooks(tool_name, tool_args, raw_result)
                            
                            result_content = final_result
                             # Log it
                            self.tool_calls_log.append({
                                "tool_name": tool_name, 
                                "arguments": tool_args, 
                                "result": final_result, 
                                "blocked": False
                            })
                            print(f"✅ Tool Executed.")

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

        return {"reply": final_reply, "tool_calls_log": self.tool_calls_log}

def run_claude_agent(user_id: str, user_message: str, guardrails: Optional[Any] = None) -> Dict[str, Any]:
    """Helper to instantiate and run Claude agent"""
    agent = ClaudePaymentAgent()
    return agent.run(user_id, user_message, guardrails)
