import urllib.request
import json

print("--- Testing ML Service API ---")
url = "http://127.0.0.1:8001/predict"

payload = {
    "drug_a": "aspirin",
    "drug_b": "warfarin",
    "text": "Increased risk of bleeding when taken together."
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

print(f"Sending POST to {url}")
print(f"Payload: {payload}")

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        result = json.loads(response.read().decode('utf-8'))
        print(f"Response: {result}")
except Exception as e:
    print(f"Request failed: {e}")
