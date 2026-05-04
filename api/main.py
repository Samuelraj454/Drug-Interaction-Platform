import asyncio
import json
import httpx
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class AnalyzeRequest(BaseModel):
    drug_a: str
    drug_b: str
    text: str = ""

@app.post("/analyse")
async def analyse_drug_interaction(request: AnalyzeRequest):
    drug_a = request.drug_a.lower().strip()
    drug_b = request.drug_b.lower().strip()
    text = request.text.strip()
    
    if not drug_a or not drug_b:
        async def err_gen():
            yield f"data: {json.dumps({'event': 'error', 'message': 'Unknown drugs / Empty input'})}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")
        
    logger.info(f"API RECEIVED REQUEST: {drug_a} + {drug_b}")

    async def sse_orchestrator():
        # 1. Fetch Severity (Fast)
        ml_url = "http://127.0.0.1:8001/predict"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(ml_url, json={"drug_a": drug_a, "drug_b": drug_b, "text": text}, timeout=3.0)
                resp.raise_for_status()
                ml_data = resp.json()
                severity = ml_data.get("severity", "Unknown")
                confidence = ml_data.get("confidence", 0.0)
                logger.info("ML PREDICTION DONE")
        except Exception as e:
            logger.error(f"ML Service Error: {e}")
            severity = "Unknown"
            confidence = 0.0
            
        # 2. Yield severity instantly (Client won't be blocked waiting for LLM)
        yield f"data: {json.dumps({'event': 'severity', 'severity': severity, 'confidence': confidence})}\n\n"
        
        # 3. Stream from GenAI Service
        genai_url = "http://127.0.0.1:8002/stream_explanation"
        try:
            logger.info("STREAMING STARTED (CONNECTING TO GENAI)")
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", genai_url, json={
                    "drug_a": drug_a, 
                    "drug_b": drug_b, 
                    "severity": str(severity), 
                    "confidence": float(confidence)
                }, timeout=15.0) as gen_resp:
                    async for chunk in gen_resp.aiter_text():
                        yield chunk
        except Exception as e:
            logger.error(f"GenAI Service Error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': 'LLM Generation failed.'})}\n\n"

    return StreamingResponse(sse_orchestrator(), media_type="text/event-stream")
