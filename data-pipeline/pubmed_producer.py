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

def run_pubmed_producer():
    print(f"Starting PubMed Producer. Pushing to Kafka Topic: {TOPIC_NAME}...")
    while True:
        try:
            # Query PubMed E-utilities
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=drug+interactions&retmode=json&retmax=1"
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            
            if id_list:
                event = {
                    "drug_a": "simvastatin",
                    "drug_b": "amiodarone",
                    "source": "pubmed",
                    "raw_text": f"Study of interaction based on pubmed ID: {id_list[0]}",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "event_id": str(uuid.uuid4())
                }
                producer.produce(TOPIC_NAME, json.dumps(event).encode('utf-8'), callback=delivery_report)
                producer.flush()
                print(f"[PubMed Producer] Sent published event from ID {id_list[0]}")
            else:
                print("[PubMed Producer] No IDs found in recent search.")
            
        except Exception as e:
            print(f"[PubMed Producer] Error: {e}")
        
        time.sleep(7)  # 7 seconds interval

if __name__ == "__main__":
    run_pubmed_producer()
