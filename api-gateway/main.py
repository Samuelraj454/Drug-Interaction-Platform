import asyncio
import json
import httpx
import logging
import os
import re
import time
import sqlite3
import aiosqlite
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from datetime import datetime
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import uuid
from prometheus_client import CollectorRegistry, Histogram, Counter, Gauge, REGISTRY, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

DRUG_LIST = []

# --- Kafka Orchestration Layer ---
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REQUEST_TOPIC = "drug-interaction-requests"
RESULT_TOPIC = "drug-interaction-results"

class KafkaManager:
    def __init__(self):
        self.producer = None
        self.consumer = None
        self.pending_requests = {} # {request_id: asyncio.Future}

    async def start(self):
        self.producer = AIOKafkaProducer(bootstrap_servers=KAFKA_SERVER)
        await self.producer.start()
        
        self.consumer = AIOKafkaConsumer(
            RESULT_TOPIC,
            bootstrap_servers=KAFKA_SERVER,
            group_id="api-gateway-group",
            auto_offset_reset="latest"
        )
        await self.consumer.start()
        asyncio.create_task(self.listen_for_results())
        logger.info("KAFKA MANAGER INITIALIZED AND LISTENING")

    async def stop(self):
        if self.producer: await self.producer.stop()
        if self.consumer: await self.consumer.stop()

    async def listen_for_results(self):
        try:
            async for msg in self.consumer:
                data = json.loads(msg.value.decode())
                req_id = data.get("request_id")
                if req_id in self.pending_requests:
                    future = self.pending_requests.pop(req_id)
                    if not future.done():
                        future.set_result(data)
        except Exception as e:
            logger.error(f"KAFKA CONSUMER CRASHED: {e}")

    async def request_interaction(self, drug_a, drug_b, text):
        req_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        payload = {
            "request_id": req_id,
            "drug_a": drug_a,
            "drug_b": drug_b,
            "text": text,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.producer.send_and_wait(REQUEST_TOPIC, json.dumps(payload).encode())
        return await asyncio.wait_for(future, timeout=30.0)

kafka_mgr = KafkaManager()

@app.on_event("startup")
async def startup_event():
    global DRUG_LIST
    await kafka_mgr.start()
    await init_db()
    try:
        # Check both local and docker paths
        data_path = "d:/drug-interaction-platform/data/drug_names.csv"
        if not os.path.exists(data_path):
             data_path = "/app/data/drug_names.csv"
             
        if os.path.exists(data_path):
            import pandas as pd
            df = pd.read_csv(data_path)
            DRUG_LIST = df.iloc[:,0].dropna().tolist()
            logger.info(f"LOADED {len(DRUG_LIST)} DRUGS FOR AUTOCOMPLETE")
    except Exception as e:
        logger.error(f"FAILED TO LOAD DRUG LIST: {e}")

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    # Explicit origins are required when allow_credentials=True
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "message": "Drug Interaction Platform API Gateway",
        "docs": "/docs",
        "health": "/health",
        "status": "online"
    }

import aiosqlite

@app.get("/metrics/summary")
async def get_metrics_summary():
    """Returns a simplified JSON of key metrics for the UI dashboard."""
    try:
        # 1. Total Interactions from DB (Async)
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT COUNT(*) FROM interactions') as cursor:
                row = await cursor.fetchone()
                total_interactions = row[0] if row else 0

        # 2. Extract stats from Prometheus REGISTRY
        stats = {
            "total_interactions": total_interactions,
            "avg_latency_ms": 0,
            "llm_ttft_sec": 0,
            "success_rate": 100.0,
            "requests_per_hr": total_interactions 
        }

        for metric in REGISTRY.collect():
            if metric.name == "api_request_latency_sec":
                m_sum = 0
                m_count = 0
                for sample in metric.samples:
                    if sample.name.endswith("_sum"): m_sum = sample.value
                    if sample.name.endswith("_count"): m_count = sample.value
                if m_count > 0:
                    stats["avg_latency_ms"] = round((m_sum / m_count) * 1000, 1)
            
            if metric.name == "llm_time_to_first_token_sec":
                for sample in metric.samples:
                    stats["llm_ttft_sec"] = round(sample.value, 2)
            
            if metric.name == "api_request_success_total":
                successes = sum(s.value for s in metric.samples)
                failures = 0
                for m2 in REGISTRY.collect():
                    if m2.name == "api_request_failure_total":
                        failures = sum(s.value for s in m2.samples)
                total = successes + failures
                if total > 0:
                    stats["success_rate"] = round((successes / total) * 100, 2)

        return stats
    except Exception as e:
        logger.error(f"Error generating metrics summary: {e}")
        return {"error": str(e)}

# --- Persistence Layer ---
DB_PATH = "/app/data/history.db"

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_a TEXT NOT NULL,
                drug_b TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                explanation TEXT,
                timestamp TEXT NOT NULL
            )
        ''')
        # Add index for performance
        await db.execute('CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp)')
        await db.commit()

# Combined above

async def save_to_db(drug_a, drug_b, severity, confidence, explanation):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                INSERT INTO interactions (drug_a, drug_b, severity, confidence, explanation, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (drug_a, drug_b, severity, confidence, explanation, datetime.now().isoformat()))
            await db.commit()
            logger.info(f"SAVED TO HISTORY: {drug_a} + {drug_b}")
    except Exception as e:
        logger.error(f"Error saving to DB: {e}")

@app.get("/history")
async def get_history():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM interactions ORDER BY id DESC LIMIT 100') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return []

@app.post("/correct")
async def register_correction(drug_a: str, drug_b: str, corrected_severity: str):
    """Stores user corrections for drug interactions to be used in retraining."""
    try:
        pair_key = tuple(sorted([drug_a.lower(), drug_b.lower()]))
        # Save to a dedicated corrections table or just update history
        # For simplicity and retraining ease, we'll use a new table
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drug_a TEXT,
                    drug_b TEXT,
                    severity TEXT,
                    timestamp TEXT
                )
            ''')
            await db.execute('''
                INSERT INTO corrections (drug_a, drug_b, severity, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (drug_a.lower(), drug_b.lower(), corrected_severity, datetime.now().isoformat()))
            await db.commit()
            
            # Invalid the cache for this pair
            if pair_key in cache:
                del cache[pair_key]
                
            logger.info(f"CORRECTION RECORDED: {drug_a} + {drug_b} -> {corrected_severity}")
            return {"status": "success", "message": f"Correction recorded for {drug_a} and {drug_b}"}
    except Exception as e:
        logger.error(f"Error saving correction: {e}")
        return {"status": "error", "message": str(e)}


# --- Metrics Definition (Aligned with Project-1.pdf SS 1) ---
API_REQUEST_LATENCY = Histogram(
    'api_request_latency_sec', 
    'Full API request latency in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
ML_MODEL_INFERENCE_LATENCY = Histogram(
    'ml_model_inference_sec', 
    'ML Service inference latency in seconds'
)
GENAI_EXPLAIN_LATENCY = Histogram(
    'genai_explain_latency_sec',
    'GenAI explanation latency in seconds'
)
RAG_RETRIEVAL_LATENCY = Histogram(
    'rag_retrieval_latency_sec',
    'RAG retrieval latency in seconds'
)
API_REQUEST_SUCCESS = Counter(
    'api_request_success_total',
    'Total successful API requests'
)
API_REQUEST_FAILURE = Counter(
    'api_request_failure_total',
    'Total failed API requests'
)
LLM_TTFT = Gauge(
    'llm_time_to_first_token_sec', 
    'LLM Time to First Token in seconds'
)
LLM_TPS = Gauge(
    'llm_tokens_per_second', 
    'LLM Tokens Per Second'
)
ML_PREDICTION_CONFIDENCE = Gauge(
    'ml_prediction_confidence', 
    'Current ML Model Prediction Confidence Score'
)
RAG_CONTEXT_COUNT = Gauge(
    'rag_context_count', 
    'Number of context chunks retrieved for RAG'
)
SEVERITY_TOTAL = Counter(
    'severity_total', 
    'Total interactions by clinical severity level',
    ['level']
)

# --- In-Memory Cache (Day 12 Optimization) ---
# Simple dictionary cache: {(drug_a, drug_b): {severity, confidence, explanation}}
# In production, use Redis or DiskCache
cache = {}

class AnalyzeRequest(BaseModel):
    drug_a: str
    drug_b: str
    text: str = ""

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/drug-suggestions")
async def get_drug_suggestions(q: str = ""):
    if not q or len(q) < 2:
        return []
    
    q_lower = q.lower()
    # Prioritize starting with q, then containing q
    starts_with = [d for d in DRUG_LIST if str(d).lower().startswith(q_lower)]
    contains = [d for d in DRUG_LIST if q_lower in str(d).lower() and d not in starts_with]
    
    return (starts_with + contains)[:10]

@app.post("/analyse")
async def analyse_drug_interaction(request: AnalyzeRequest):
    start_time = time.time()
    drug_a = request.drug_a.lower().strip()
    drug_b = request.drug_b.lower().strip()
    text = request.text.strip()
    
    pair_key = tuple(sorted([drug_a, drug_b]))

    if not drug_a or not drug_b:
        API_REQUEST_FAILURE.inc()
        async def err_gen():
            yield f"data: {json.dumps({'event': 'error', 'message': 'Unknown drugs / Empty input'})}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    # Check Cache (Optimization) - With Safety Check
    if pair_key in cache:
        cached_data = cache[pair_key]
        # Only use cache if it has a meaningful explanation
        if len(cached_data.get('explanation', '')) > 20:
            logger.info(f"CACHE HIT (VALID): {pair_key}")
            async def cache_gen():
                yield f"data: {json.dumps({'event': 'severity', 'severity': cached_data['severity'], 'confidence': cached_data['confidence']})}\n\n"
                # Optimization: yield in larger chunks for immediate UI responsiveness
                explanation = cached_data['explanation']
                chunk_size = 30
                for i in range(0, len(explanation), chunk_size):
                    yield f"data: {json.dumps({'event': 'token', 'text': explanation[i:i+chunk_size]})}\n\n"
                    await asyncio.sleep(0.01) # Small delay to mimic live flow
            
            # Metrics for cache hits
            API_REQUEST_SUCCESS.inc()
            SEVERITY_TOTAL.labels(level=cached_data['severity']).inc()
            
            return StreamingResponse(cache_gen(), media_type="text/event-stream")

    logger.info(f"API RECEIVED REQUEST: {drug_a} + {drug_b}")

    async def finalize_request(da, db, sev, conf, expl, key, start_t):
        if sev != "Unknown" and len(expl) > 20:
            cache[key] = {"severity": sev, "confidence": conf, "explanation": expl}
            await save_to_db(da, db, sev, conf, expl)
            API_REQUEST_SUCCESS.inc()
            SEVERITY_TOTAL.labels(level=sev).inc()
            logger.info(f"REQUEST FINALIZED: {da} + {db} ({sev})")
        
        API_REQUEST_LATENCY.observe(time.time() - start_t)

    async def sse_orchestrator():
        full_explanation = ""
        severity = "Unknown"
        confidence = 0.0
        
        try:
            # Phase 1: Event-Driven Kafka Pipeline (High Consistency)
            try:
                logger.info(f"TRIGGERING KAFKA PIPELINE: {drug_a} + {drug_b}")
                result = await kafka_mgr.request_interaction(drug_a, drug_b, text)
                severity = result.get("severity", "Unknown")
                confidence = result.get("confidence", 0.0)
                full_explanation = result.get("explanation", "")

                # Send Severity Event
                yield f"data: {json.dumps({'event': 'severity', 'severity': severity, 'confidence': confidence})}\n\n"
                
                # Stream tokens from the Kafka result
                words = full_explanation.split(" ")
                for i in range(0, len(words), 3):
                    chunk = " ".join(words[i:i+3]) + " "
                    yield f"data: {json.dumps({'event': 'token', 'text': chunk})}\n\n"
                    await asyncio.sleep(0.03)
                
                logger.info(f"KAFKA PIPELINE SUCCESS: {drug_a} + {drug_b}")
                await finalize_request(drug_a, drug_b, severity, confidence, full_explanation, pair_key, start_time)
                return # Exit early after successful Kafka path

            except Exception as kafka_e:
                logger.warning(f"Kafka Pipeline Failed/Timed out: {kafka_e}. Falling back to HTTP Stream.")

            # Phase 2: Direct HTTP Streaming Fallback (Real-time Tokens)
            genai_url = os.getenv("GENAI_SERVICE_URL", "http://genai_service:8080") + "/stream_explanation"
            llm_start_time = time.time()
            first_token_received = False
            
            async with httpx.AsyncClient(trust_env=False, timeout=45.0) as client:
                async with client.stream("POST", genai_url, json={
                    "drug_a": drug_a, 
                    "drug_b": drug_b, 
                    "severity": str(severity), 
                    "confidence": float(confidence)
                }) as gen_resp:
                    if gen_resp.status_code != 200:
                        raise Exception(f"GenAI Service returned {gen_resp.status_code}")

                    async for line in gen_resp.aiter_lines():
                        if not line.strip(): continue
                        
                        if not first_token_received:
                            ttft = time.time() - llm_start_time
                            LLM_TTFT.set(ttft)
                            GENAI_EXPLAIN_LATENCY.observe(ttft)
                            first_token_received = True

                        yield f"{line}\n\n"
                        
                        # Parse events for caching/logging
                        try:
                            if line.startswith("data:"):
                                json_str = re.sub(r'^data:\s*', '', line).strip()
                                if not json_str: continue
                                d = json.loads(json_str)
                                
                                if d.get("event") == "token":
                                    full_explanation += d.get("text", "")
                                elif d.get("event") == "severity":
                                    severity = d.get("severity", severity)
                                    confidence = float(d.get("confidence", confidence))
                                elif d.get("event") == "metrics":
                                    rag_lat = d.get("rag_retrieval_latency_sec", 0.0)
                                    RAG_RETRIEVAL_LATENCY.observe(rag_lat)
                        except Exception as e:
                            logger.error(f"SSE Parse Error: {e}")
            
            logger.info(f"HTTP FALLBACK SUCCESS: {drug_a} + {drug_b}")
            await finalize_request(drug_a, drug_b, severity, confidence, full_explanation, pair_key, start_time)

        except Exception as e:
            logger.error(f"Critical Orchestration Error: {e}")
            API_REQUEST_FAILURE.inc()
            yield f"data: {json.dumps({'event': 'error', 'message': f'Analysis failed: {str(e)}'})}\n\n"
        finally:
            total_latency = time.time() - start_time
            logger.info(f"REQUEST FLOW ENDED: {total_latency:.2f}s")

    return StreamingResponse(sse_orchestrator(), media_type="text/event-stream")