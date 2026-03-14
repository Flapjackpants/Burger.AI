import requests
import json
import time

BASE_URL = "http://localhost:5001"

def run_test():
    print("--- STARTING TEST WORKFLOW ---")
    
    # 1. Get Company LLM Config
    print("\n[Step 1] Fetching Company LLM Config...")
    try:
        response = requests.get(f"{BASE_URL}/company/config")
        if response.status_code == 200:
            config = response.json()
            print("Config received successfully:")
            print(json.dumps(config, indent=2))
        else:
            print(f"Failed to get config: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Is it running?")
        return

    # 2. Generate Red Team Test Cases
    print("\n[Step 2] Generating Red Team Test Cases (Category: PII/Sensitive Leak)...")
    payload = {
        "category": "PII/Sensitive Leak",
        "num_cases": 1,
        "llm_config": config
    }
    
    try:
        # Increased timeout as OpenAI call might take a few seconds
        response = requests.post(f"{BASE_URL}/red-team/generate-test-cases", json=payload, timeout=60)
        if response.status_code == 200:
            test_cases_data = response.json()
            test_cases = test_cases_data.get("test_cases", {})
            
            # Navigate the structure based on how redTeamLLM returns it
            if "PII/Sensitive Leak" in test_cases:
                cases = test_cases["PII/Sensitive Leak"]
            elif isinstance(test_cases, list):
                cases = test_cases
            elif isinstance(test_cases, dict):
                # Handle dictionary like {"test_case_1": {...}, "test_case_2": {...}}
                print("Parsing dictionary test cases...")
                cases = list(test_cases.values())
            else:
                 # Fallback
                 cases = []
                 print("Structure unexpected:", test_cases)

            if cases:
                first_case = cases[0]
                print(f"Generated {len(cases)} test cases.")
                print(f"Using First Case Prompt: '{first_case['prompt']}'")
            else:
                print("No test cases generated.")
                return
        else:
            print(f"Failed to generate test cases: {response.text}")
            return
    except Exception as e:
        print(f"Error generating test cases: {e}")
        return

    # 3. Attack the Company Model
    attack_prompt = first_case['prompt']
    print(f"\n[Step 3] Attacking Company Model with Prompt: '{attack_prompt}'...")
    
    chat_payload = {"prompt": attack_prompt}
    try:
        response = requests.post(f"{BASE_URL}/company/chat", json=chat_payload)
        if response.status_code == 200:
            model_response = response.json().get("response", "")
            print(f"Company Model Response: '{model_response}'")
        else:
            print(f"Failed to get response from company model: {response.text}")
            return
    except Exception as e:
        print(f"Error chatting with company model: {e}")
        return

    # 4. Evaluate the Interaction
    print("\n[Step 4] Evaluating the Interaction...")
    eval_payload = {
        "category": "PII/Sensitive Leak",
        "prompt": attack_prompt,
        "response": model_response,
        "llm_config": config
    }
    
    try:
        response = requests.post(f"{BASE_URL}/evaluator/evaluate", json=eval_payload, timeout=60)
        if response.status_code == 200:
            evaluation = response.json().get("evaluation", {})
            print("Evaluation Result:")
            print(json.dumps(evaluation, indent=2))
            
            if evaluation.get("passed"):
                print("\n✅ RESULT: PASSED (The model defended successfully)")
            else:
                print("\n❌ RESULT: FAILED (The attack succeeded)")
        else:
            print(f"Failed to evaluate: {response.text}")
            return
    except Exception as e:
        print(f"Error evaluating: {e}")
        return

if __name__ == "__main__":
    # Wait a moment for server to fully initialize if just started
    time.sleep(2)
    run_test()
