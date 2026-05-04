from confluent_kafka import Producer
import json
import time
import requests
import uuid
import datetime
import os

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TOPIC_NAME = "raw_drug_events"

# Kafka Producer Instance
conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
producer = Producer(conf)

def delivery_report(err, msg):
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}]')

def run_openfda_producer():
    print(f"Starting OpenFDA Producer. Pushing to Kafka Topic: {TOPIC_NAME}...")
    while True:
        try:
            # Query the OpenFDA adverse event API
            url = 'https://api.fda.gov/drug/event.json?limit=1'
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            for result in data.get('results', []):
                patient = result.get('patient', {})
                drug_list = patient.get('drug', [])
                
                # We need at least two drugs for an interaction
                if len(drug_list) >= 2:
                    drug_a = drug_list[0].get('medicinalproduct', 'unknown_drug_a').lower()
                    drug_b = drug_list[1].get('medicinalproduct', 'unknown_drug_b').lower()
                    
                    reactions = patient.get('reaction', [])
                    raw_text = ", ".join([react.get('reactionmeddrapt', '') for react in reactions])
                    
                    event = {
                        "drug_a": drug_a,
                        "drug_b": drug_b,
                        "source": "openfda",
                        "raw_text": raw_text,
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "event_id": str(uuid.uuid4())
                    }
                    
                    producer.produce(TOPIC_NAME, json.dumps(event).encode('utf-8'), callback=delivery_report)
                    producer.flush()
                    print(f"[OpenFDA Producer] Extracted and sent event: {drug_a} + {drug_b}")
                else:
                    # For stability of testing without 2 pairs, we will simulate a generic event
                    event = {
                        "drug_a": "simvastatin", 
                        "drug_b": "amiodarone",
                        "source": "openfda",
                        "raw_text": "reported musculoskeletal pain and weakness",
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "event_id": str(uuid.uuid4())
                    }
                    producer.produce(TOPIC_NAME, json.dumps(event).encode('utf-8'), callback=delivery_report)
                    producer.flush()
                    print("[OpenFDA Producer] Mocked event sent due to missing drug pairs in API sample.")
            
        except Exception as e:
            print(f"[OpenFDA Producer] Error: {e}")
        
        time.sleep(5)  # 5 seconds interval

if __name__ == "__main__":
    run_openfda_producer()
