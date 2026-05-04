from confluent_kafka import Consumer, Producer, KafkaException
import time
import json
import joblib
import os
import numpy as np
from prometheus_client import start_http_server, Gauge, Counter

# --- Metrics ---
KAFKA_LAG = Gauge('kafka_consumer_lag_items', 'Unprocessed items in Kafka Topic')
CONSUMER_ERRORS = Counter('consumer_process_errors_total', 'Total errors in consumer processing')

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TOPIC_RAW = "raw_drug_events"
TOPIC_PROCESSED = "processed_features"

# Load artifacts
data_dir = os.getenv('DATA_DIR', 'd:/drug-interaction-platform/data')
try:
    print("Loading ML artifacts...")
    tfidf = joblib.load(os.path.join(data_dir, 'tfidf.joblib'))
    drug_counts = joblib.load(os.path.join(data_dir, 'drug_counts.joblib'))
    # Start Prometheus exporter
    start_http_server(8001)
    print("Prometheus metrics server started on port 8001")
except Exception as e:
    print(f"Failed to load artifacts or start metrics. Error: {e}")
    exit(1)

def run_consumer():
    # Kafka Consumer Configuration
    conf_consumer = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'feature-engineering-group',
        'auto.offset.reset': 'earliest'
    }
    consumer = Consumer(conf_consumer)
    
    # Kafka Producer Configuration (to push processed features)
    conf_producer = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
    producer = Producer(conf_producer)

    print(f"Started Feature Engineering Consumer. Listening on Topic: {TOPIC_RAW}...")
    consumer.subscribe([TOPIC_RAW])

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue
                else:
                    print(f"Kafka Error: {msg.error()}")
                    CONSUMER_ERRORS.inc()
                    continue

            try:
                # Decode message
                data = json.loads(msg.value().decode('utf-8'))
                print(f"[Consumer] Recv Event: {data.get('drug_a')} + {data.get('drug_b')}")

                # Preprocessing
                drug_a = data.get('drug_a', '').lower().strip()
                drug_b = data.get('drug_b', '').lower().strip()
                text = data.get('raw_text', '')

                # Basic features
                text_len = len(text)
                freq_a = drug_counts.get(drug_a, 0)
                freq_b = drug_counts.get(drug_b, 0)
                X_basic = np.array([[text_len, freq_a, freq_b]])

                # TFIDF text features
                X_text = tfidf.transform([text]).toarray()

                # Final Array
                X_final = np.hstack([X_basic, X_text])
                features_list = [float(x) for x in X_final[0]]

                output_event = {
                    "event_id": data.get('event_id', 'unknown'),
                    "drug_a": drug_a,
                    "drug_b": drug_b,
                    "source": data.get('source', 'unknown'),
                    "feature_vector": json.dumps(features_list)
                }

                # Produce to processed topic
                producer.produce(TOPIC_PROCESSED, json.dumps(output_event).encode('utf-8'))
                producer.flush()
                print(f" -> Processed & Pushed to Kafka Topic: {TOPIC_PROCESSED}")

            except Exception as ee:
                print(f"Error processing message: {ee}")
                CONSUMER_ERRORS.inc()

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == "__main__":
    run_consumer()
