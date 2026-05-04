import httpx
import sys

def test_stream():
    url = "http://127.0.0.1:8002/analyse"
    payload = {
        "drug_a": "aspirin",
        "drug_b": "warfarin",
        "text": ""
    }
    
    print(f"--- TESTING GENAI SSE STREAM AT {url} ---")
    
    try:
        # We use a context block to securely handle streaming data buffers
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
                        
                    # Standard stdout print to visualize token-by-token processing
                    print(content, end="", flush=True)
                    
    except Exception as e:
        print(f"\nStream Test Failed: {e}")

if __name__ == "__main__":
    test_stream()
