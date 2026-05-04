from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
import asyncio

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_expert_clinical_data(drug_a, drug_b):
    """Returns structured expert clinical data for known drug pairs."""
    pair = sorted([drug_a.lower().strip(), drug_b.lower().strip()])
    
    if pair == ["aspirin", "warfarin"]:
        return {
            "severity": "Severe",
            "type": "Pharmacodynamic",
            "mechanism": [
                "Additive anticoagulant + antiplatelet effects",
                "Platelet inhibition (Aspirin) + clotting factor suppression (Warfarin)",
                "Aspirin may displace Warfarin from protein binding sites, increasing free drug concentration"
            ],
            "risk": "Increased risk of major bleeding, including gastrointestinal and systemic hemorrhage.",
            "evidence": "High",
            "confidence": 0.95,
            "recommendation": "Use combination only if clinically necessary. Monitor INR closely and watch for signs of bleeding.",
            "why": "This interaction occurs due to pharmacodynamic synergy where both drugs impair different parts of the hemostatic process. Additionally, the pharmacokinetic displacement from albumin increases the active fraction of Warfarin, further compounding the bleeding risk.",
            "genetic_factors": "CYP2C9 and VKORC1 variants significantly impact Warfarin metabolism and sensitivity, potentially exacerbating this interaction."
        }
    return None

@app.post("/analyse")
async def analyse(request: Request):
    data = await request.json()
    drug_a = data.get("drug_a")
    drug_b = data.get("drug_b")
    logger.info(f"MOCK ANALYSE REQUEST: {drug_a} + {drug_b}")
    
    async def generate():
        expert_data = get_expert_clinical_data(drug_a, drug_b)
        if expert_data:
            yield f"data: {json.dumps({'event': 'clinical_data', 'data': expert_data})}\n\n"
            await asyncio.sleep(0.5)
            
            explanation = f"Expert System Analysis: {expert_data['why']}\n\nGenetic Considerations: {expert_data['genetic_factors']}"
            for token in explanation.split(" "):
                yield f"data: {json.dumps({'event': 'token', 'text': token + ' '})}\n\n"
                await asyncio.sleep(0.05)
        else:
            yield f"data: {json.dumps({'event': 'severity', 'severity': 'Moderate', 'confidence': 0.72})}\n\n"
            await asyncio.sleep(0.5)
            explanation = f"Generic analysis for {drug_a} and {drug_b}. Potential interaction detected."
            for token in explanation.split(" "):
                yield f"data: {json.dumps({'event': 'token', 'text': token + ' '})}\n\n"
                await asyncio.sleep(0.1)
            
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/metrics/summary")
async def metrics():
    return {
        "total_interactions": 1420,
        "avg_latency_ms": 98,
        "llm_ttft_sec": 0.8,
        "success_rate": 100,
        "requests_per_hr": 12
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
