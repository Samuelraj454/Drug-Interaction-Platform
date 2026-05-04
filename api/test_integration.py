import httpx
import sys
import json
import time

def test_integration():
    url = "http://127.0.0.1:8000/analyse"
    payload = {
        "drug_a": "aspirin",
        "drug_b": "warfarin",
        "text": ""
    }
    
    print(f"--- TESTING UNIFIED PIPELINE AT {url} ---")
    start_time = time.time()
    
    try:
        with httpx.stream("POST", url, json=payload, timeout=10.0) as response:
            if response.status_code != 200:
                print(f"Failed! Code: {response.status_code}\nOutput: {response.read()}")
                return
                
            print("Connected! Streaming Response Initialized:\n")
            
            for line in response.iter_lines():
                if line.startswith("data: "):
                    content = line[6:]
                    
                    if content == "[DONE]":
                        print("\n\n[SSE SIGNAL: STREAM FINISHED]")
                        break
                        
                    try:
                        parsed = json.loads(content)
                        if parsed.get("event") == "severity":
                            elapsed = time.time() - start_time
                            print(f"[INSTANT ML RESULT ({elapsed:.2f}s)]: Severity {parsed.get('severity')} | Confidence {parsed.get('confidence')}")
                            print("\n[STARTING LLM STREAM...]")
                        elif parsed.get("event") == "token":
                            print(parsed.get("text", ""), end="", flush=True)
                        elif parsed.get("event") == "error":
                            print(f"\n[ERROR]: {parsed.get('message')}")
                    except json.JSONDecodeError:
                        print(content, end="", flush=True)
                        
    except Exception as e:
        print(f"\nStream Test Failed: {e}")

if __name__ == "__main__":
    test_integration()
