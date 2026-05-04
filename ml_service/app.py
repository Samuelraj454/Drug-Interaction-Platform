from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import numpy as np
import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from contextlib import asynccontextmanager
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import asyncio
import json
import time
from prometheus_client import Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# --- Prometheus Metrics ---
ML_INFERENCE_LATENCY = Histogram(
    "ml_model_inference_sec",
    "Time spent running model inference",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)
ML_REQUEST_COUNT = Counter(
    "ml_requests_total",
    "Total number of ML prediction requests",
    ["status"]
)

# Global variables for model and artifacts
model = None
tokenizer = None
tfidf = None
drug_counts = None
is_transformer = False

# Mapping
SEVERITIES = ["None", "Mild", "Moderate", "Severe", "Contraindicated"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, tokenizer, tfidf, drug_counts, is_transformer
    data_dir = "./data" # Simplified for local/docker relative path
    transformer_path = os.path.join(data_dir, "transformer_model")
    
    # 1. Try to load BioBERT Transformer Model
    if os.path.exists(transformer_path):
        try:
            print("Loading BioBERT model...")
            model = AutoModelForSequenceClassification.from_pretrained(transformer_path)
            tokenizer = AutoTokenizer.from_pretrained(transformer_path)
            model.eval()
            is_transformer = True
            print("BioBERT model loaded successfully!")
        except Exception as e:
            print(f"Error loading BioBERT: {e}")

    # 2. Fallback to Legacy Random Forest (Artifacts check)
    if not is_transformer:
        try:
             # Check if data files exist
             if os.path.exists(os.path.join(data_dir, "model.joblib")):
                model = joblib.load(os.path.join(data_dir, "model.joblib"))
                tfidf = joblib.load(os.path.join(data_dir, "tfidf.joblib"))
                drug_counts = joblib.load(os.path.join(data_dir, "drug_counts.joblib"))
                print("Legacy ML model loaded.")
        except Exception as e:
            print(f"Error loading legacy artifacts: {e}")
    
    # Start Kafka Worker
    asyncio.create_task(kafka_worker())
    yield

app = FastAPI(lifespan=lifespan)

class PredictRequest(BaseModel):
    drug_a: str
    drug_b: str
    text: str = ""

@app.get("/status")
async def get_status():
    global model, is_transformer
    return {
        "status": "ready" if model else "degraded",
        "model_type": "BioBERT_Transformer" if is_transformer else "Legacy_RandomForest",
        "artifacts_found": {
            "transformer": os.path.exists("./data/transformer_model"),
            "legacy_model": os.path.exists("./data/model.joblib"),
            "tfidf": os.path.exists("./data/tfidf.joblib"),
            "drug_counts": os.path.exists("./data/drug_counts.joblib")
        },
        "device": str(next(model.parameters()).device) if is_transformer and model else "cpu"
    }

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/predict")
async def predict(request: PredictRequest):
    ML_REQUEST_COUNT.labels(status="received").inc()
    result = await run_inference(request.drug_a, request.drug_b, request.text)
    if "error" in result:
        ML_REQUEST_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=result["error"])
    ML_REQUEST_COUNT.labels(status="success").inc()
    return result

async def run_inference(drug_a: str, drug_b: str, text: str):
    global model, tokenizer, tfidf, drug_counts, is_transformer
    
    with ML_INFERENCE_LATENCY.time():
        if not model:
            return {"error": "Model not loaded"}
    
        if is_transformer:
            try:
                inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
                with torch.no_grad():
                    outputs = model(**inputs)
                    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                    confidence, predicted_class = torch.max(probabilities, dim=-1)
                    
                return {
                    "severity": SEVERITIES[predicted_class.item()],
                    "confidence": float(confidence.item()),
                    "legacy_mode": False
                }
            except Exception as e:
                return {"error": f"Transformer inference error: {str(e)}"}
        else:
            try:
                # Legacy Random Forest logic
                text_length = len(text)
                freq_drug_a = drug_counts.get(drug_a, 0) if drug_counts else 0
                freq_drug_b = drug_counts.get(drug_b, 0) if drug_counts else 0
                
                X_basic = np.array([[text_length, freq_drug_a, freq_drug_b]])
                X_text = tfidf.transform([text]).toarray()
                X_final = np.hstack([X_basic, X_text])
                
                probabilities = model.predict_proba(X_final)[0]
                confidence = float(np.max(probabilities))
                pred_label = int(model.predict(X_final)[0])
    
                if pred_label == 0:
                    severity_label = "None"
                else:
                    if confidence >= 0.95: severity_label = "Contraindicated"
                    elif confidence >= 0.80: severity_label = "Severe"
                    elif confidence >= 0.50: severity_label = "Moderate"
                    else: severity_label = "Mild"
    
                return {
                    "severity": severity_label,
                    "confidence": confidence,
                    "legacy_mode": True
                }
            except Exception as e:
                return {"error": f"Legacy inference error: {str(e)}"}

async def kafka_worker():
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    try:
        consumer = AIOKafkaConsumer(
            "drug-interaction-requests",
            bootstrap_servers=bootstrap_servers,
            group_id="ml-service-group",
            auto_offset_reset="earliest"
        )
        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)

        await consumer.start()
        await producer.start()
        
        print(f"Kafka worker started, listening on analysis-requests...")
        
        try:
            async for msg in consumer:
                try:
                    data = json.loads(msg.value.decode('utf-8'))
                    drug_a = data.get("drug_a")
                    drug_b = data.get("drug_b")
                    text = data.get("text", "")
                    
                    ML_REQUEST_COUNT.labels(status="success").inc()
                    result = await run_inference(drug_a, drug_b, text)
                    result["request_id"] = data.get("request_id")
                    result["drug_a"] = drug_a
                    result["drug_b"] = drug_b
                    
                    await producer.send_and_wait("drug-interaction-ml-predictions", json.dumps(result).encode('utf-8'))
                except Exception as e:
                    print(f"Error processing Kafka message: {e}")
        finally:
            await consumer.stop()
            await producer.stop()
    except Exception as e:
        print(f"Kafka worker failed to start: {e}")
