from typing import Any, List, Dict, Optional, Tuple
import json

class GuardrailEngine:
    """
    A portable engine that applies dynamic safety rules to ANY agent's tool execution.
    It doesn't care which LLM model is used; it only looks at the inputs (args) and outputs (result).
    """

    def __init__(self, rules: List[Dict[str, Any]]):
        self.rules = rules or []

    def check_pre_hook(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check if a tool call should be blocked BEFORE execution.
        Returns: (is_blocked, error_message)
        """
        for rule in self.rules:
            if rule.get("type") != "pre_hook":
                continue
                
            # Check if rule applies to this tool
            target_tool = rule.get("tool_name", "*")
            if target_tool != "*" and target_tool != tool_name:
                continue
            
            # Evaluate condition
            condition = rule.get("condition", "False")
            try:
                # Safe eval context with minimal globals
                safe_locals = {"args": args, "tool_name": tool_name}
                if eval(condition, {"__builtins__": {}}, safe_locals):
                    return True, rule.get("message", "Action blocked by security guardrail.")
            except Exception as e:
                print(f"[GuardrailEngine] Pre-hook Check Error: {e}")
        
        return False, None

    def apply_post_hooks(self, tool_name: str, args: Dict[str, Any], result: Any) -> Any:
        """
        Modify or block the result AFTER execution but BEFORE the model sees it.
        Returns: Modified result
        """
        current_result = result
        
        for rule in self.rules:
            if rule.get("type") != "post_hook":
                continue

            target_tool = rule.get("tool_name", "*")
            if target_tool != "*" and target_tool != tool_name:
                continue
            
            condition = rule.get("condition", "False")
            try:
                safe_locals = {"args": args, "result": current_result, "tool_name": tool_name, "str": str}
                if eval(condition, {"__builtins__": {}, "str": str}, safe_locals):
                    action = rule.get("action")
                    
                    if action == "block_result":
                        return {"error": rule.get("message", "Result blocked by guardrail")}
                    
                    elif action == "redact_field":
                        target_field = rule.get("target_field")
                        replacement = rule.get("replacement", "<REDACTED>")
                        
                        if isinstance(current_result, dict) and target_field in current_result:
                            # Verify if we need to deep copy to avoid mutation side effects? 
                            # For simple dicts, this is fine.
                            current_result[target_field] = replacement
                            
            except Exception as e:
                print(f"[GuardrailEngine] Post-hook Error: {e}")
                
        return current_result
