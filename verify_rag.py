import requests
import json
import time

API_URL = "http://localhost:8000/analyse"

def test_interaction(drug_a, drug_b):
    print(f"\n{'='*50}")
    print(f"TESTING: {drug_a} + {drug_b}")
    print(f"{'='*50}")
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, json={
            "drug_a": drug_a,
            "drug_b": drug_b,
            "text": ""
        }, stream=True, timeout=30)
        
        severity = None
        confidence = None
        full_text = ""
        
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data = json.loads(decoded_line[6:])
                    event = data.get("event")
                    
                    if event == "severity":
                        severity = data.get("severity")
                        confidence = data.get("confidence")
                        print(f"[RESULT] Severity: {severity} | Confidence: {confidence*100:.1f}%")
                    elif event == "token":
                        full_text += data.get("text", "")
                    elif event == "error":
                        print(f"[ERROR] {data.get('message')}")
        
        print(f"\n[EXPLANATION] Length: {len(full_text)}")
        print(f"{full_text[:200]}...")
        print(f"\n[LATENCY] {time.time() - start_time:.2f}s")
        
        return {
            "severity": severity,
            "text": full_text
        }
    except Exception as e:
        print(f"[CRITICAL ERROR] {e}")
        return None

if __name__ == "__main__":
    # Test Case 1: Known High Risk
    res1 = test_interaction("aspirin", "warfarin")
    
    # Test Case 2: Known Safe/Mild
    res2 = test_interaction("paracetamol", "ibuprofen")
    
    # Test Case 3: Unknown/Brand Names
    res3 = test_interaction("dolo 650", "dolokind plus")
    
    print("\n\n" + "#"*50)
    print("FINAL VALIDATION")
    print("#"*50)
    
    if res1 and res2 and res3:
        diff_1_2 = res1['text'] != res2['text']
        diff_2_3 = res2['text'] != res3['text']
        
        print(f"Explanation 1 != Explanation 2: {diff_1_2}")
        print(f"Explanation 2 != Explanation 3: {diff_2_3}")
        
        if diff_1_2 and diff_2_3:
            print("\nSUCCESS: The system is producing unique and specific explanations!")
        else:
            print("\nFAILURE: Some explanations are still identical.")
    else:
        print("\nTEST FAILED: Could not reach API. Ensure services are running.")
