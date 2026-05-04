import redis

try:
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    print("\n--- VALIDATING RAW STREAM (raw_drug_events) ---")
    raw = r.xrange("raw_drug_events", min="-", max="+", count=2)
    for msg_id, data in raw:
        print(f"[{msg_id}] {data}")
        
    print("\n--- VALIDATING PROCESSED STREAM (processed_features) ---")
    processed = r.xrange("processed_features", min="-", max="+", count=2)
    for msg_id, data in processed:
        feats = data.get('feature_vector', '[]')
        print(f"[{msg_id}] {data.get('drug_a')} + {data.get('drug_b')} | features logic active (vector len: {len(feats)})")
        
except Exception as e:
    print(f"Error during validation: {e}")
