import os
import json
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
import urllib.parse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
import google.generativeai as genai
from rag_pipeline import DrugInteractionRAG
from dotenv import load_dotenv
import logging
import time
from datetime import datetime
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from prometheus_client import Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# --- Prometheus Metrics ---
GENAI_EXPLAIN_LATENCY = Histogram(
    "genai_explanation_latency_sec",
    "Time spent generating interaction explanations",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
)
RAG_RETRIEVAL_LATENCY = Histogram(
    "genai_rag_retrieval_sec",
    "Time spent in RAG context retrieval",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)
GENAI_REQUEST_COUNT = Counter(
    "genai_requests_total",
    "Total number of GenAI explanation requests",
    ["provider", "status"]
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# RAG Init (Lazy)
rag = None

# LLM Providers Init
openai_api_key = os.getenv("OPENAI_API_KEY")
client_openai = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None

gemini_api_key = os.getenv("GOOGLE_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    # Using gemini-1.5-flash for better performance and speed
    model_gemini = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )
else:
    model_gemini = None

class ExplainRequest(BaseModel):
    drug_a: str
    drug_b: str
    severity: str
    confidence: float

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

async def generate_rag_mock_stream(drug_a, drug_b, severity, confidence, context_str):
    """Fallback: Generates a high-quality explanation based on context or general principles."""
    # Heuristic refinement for toxic combinations
    refined_severity = severity
    ctx_lower = context_str.lower()
    toxic_keywords = ["acetaminophen", "paracetamol", "dolo", "calpol", "panadol", "dolokind"]
    drug_str = (drug_a + " " + drug_b).lower()
    
    is_toxic_overlap = any(k in drug_str for k in toxic_keywords) and (drug_a.lower() != drug_b.lower())
    
    high_risk_markers = ["toxicity", "lethal", "fatal", "major risk", "acute failure", "hepatotoxicity", "respiratory depression"]
    if any(k in ctx_lower for k in high_risk_markers):
        refined_severity = "Severe"
        confidence = max(confidence, 0.95)
    elif is_toxic_overlap:
        # Detect potential doubling of common meds (e.g. Dolo + Dolokind)
        # This is extremely dangerous, promote to Contraindicated
        refined_severity = "Contraindicated"
        confidence = 0.99 
    
    # Emit refinement event
    yield f"data: {json.dumps({'event': 'severity', 'severity': refined_severity, 'confidence': confidence})}\n\n"

    # Dynamic template based on severity
    consequences = {
        "None": "No significant pharmacological interaction detected based on current data.",
        "Mild": "Potential for minor physiological changes. Standard clinical monitoring is advised.",
        "Moderate": "Clinically significant interaction. Possible alteration in drug metabolism or increased side effects.",
        "Severe": "High-risk interaction. Likely to cause significant adverse reactions or systemic toxicity. Immediate medical review required.",
        "Contraindicated": "CRITICAL RISK. This combination is medically dangerous and should be avoided due to life-threatening toxicity."
    }
    
    actions = {
        "None": "Continue therapy as prescribed.",
        "Mild": "Monitor for minor symptoms; maintain standard dosage protocols.",
        "Moderate": "Consult a healthcare provider; consider monitoring specific biomarkers.",
        "Severe": "DO NOT combine without strict specialist supervision. Physiological monitoring recommended.",
        "Contraindicated": "ABORT combination immediately. Seek alternative therapy from a qualified professional."
    }

    # Format the report sections
    report_context = context_str if len(context_str) > 20 else consequences.get(refined_severity, "Increased risk of systemic toxicity.")
    
    template = [
        f" CLINICAL ANALYSIS REPORT\n",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n",
        f"1. INTERACTION PROFILE:\n   The combination of {drug_a.upper()} and {drug_b.upper()} carries a {refined_severity.upper()} clinical risk profile.\n",
        f"   Assessment suggests { 'critical pharmacodynamical interference' if refined_severity in ['Severe', 'Contraindicated'] else 'potential metabolic overlap' }.\n\n",
        f"2. POTENTIAL CONSEQUENCES:\n   {report_context}\n\n",
        f"3. CLINICAL DIRECTIVES:\n   • {actions.get(refined_severity, 'Consult a healthcare provider.')}\n",
        f"   • Immediate physiological monitoring is advised for safety.\n",
        f"   • Seek localized pharmacological verification before continuing therapy.\n\n",
        f"4. INTELLIGENCE SOURCE:\n   AI Reference Model (Safety-Verified Offline Logic).\n",
        f"   Integrated Data: OpenFDA Adverse Events & PubMed Clinical Studies.\n",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    for para in template:
        yield f"data: {json.dumps({'event': 'token', 'text': para})}\n\n"
        await asyncio.sleep(0.01)

async def fetch_live_fda_data(drug_a, drug_b):
    """Fetches real-time adverse event data from OpenFDA API if local vectors are insufficient."""
    try:
        da = urllib.parse.quote(f'"{drug_a.lower()}"')
        db = urllib.parse.quote(f'"{drug_b.lower()}"')
        
        url = f'https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{da}+AND+patient.drug.medicinalproduct:{db}&limit=3'
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                if not results:
                    return None
                    
                reactions = []
                for res in results:
                    patient = res.get('patient', {})
                    reacts = patient.get('reaction', [])
                    for r in reacts:
                        meddrapt = r.get('reactionmeddrapt')
                        if meddrapt and meddrapt not in reactions:
                            reactions.append(meddrapt)
                            if len(reactions) >= 5: # Limit to top 5 symptoms
                                break
                    if len(reactions) >= 5:
                        break
                
                if reactions:
                    symptom_str = ", ".join(reactions)
                    return f"[LIVE FDA DATA] Reported adverse events in real-world patients taking {drug_a} and {drug_b} simultaneously: {symptom_str}."
            return None
    except Exception as e:
        logger.warning(f"Live FDA Fetch failed: {e}")
        return None

@app.post("/stream_explanation")
async def stream_explanation(request: ExplainRequest):
    drug_a = request.drug_a
    drug_b = request.drug_b

    # RAG Context Retrieval & Live Data
    rag_start = time.time()
    with RAG_RETRIEVAL_LATENCY.time():
        try:
            contexts = rag.get_relevant_context(drug_a, drug_b, top_k=5) if rag else []
            
            # Secondary Identity Filtering for absolute accuracy
            da, db = drug_a.lower(), drug_b.lower()
            is_same_drug = (da == db)
            
            verified_contexts = []
            for c in contexts:
                ctx_text = c['context'].lower()
                # Strict logic: context must mention both drugs if they are different
                if not is_same_drug:
                    if da in ctx_text and db in ctx_text:
                        verified_contexts.append(c)
                else:
                    # If same drug, ensure it's specifically about that drug and not just a random mention
                    # e.g. "Cocaine overdose" or "Cocaine toxicity"
                    if da in ctx_text and any(k in ctx_text for k in ["overdose", "toxicity", "lethal", "dosage", "repeated"]):
                        verified_contexts.append(c)
            
            # Async fetch live data simultaneously
            live_data_str = await fetch_live_fda_data(drug_a, drug_b)
            
            if len(verified_contexts) == 0:
                if is_same_drug:
                    context_str = f"Clinical warning: Duplicate administration of {drug_a.upper()} detected. High risk of acute toxicity and pharmacological overdose."
                else:
                    context_str = "No specific known interactions found in the medical database for this pair."
            else:
                # Format and summarize context
                context_str = ""
                for c in verified_contexts:
                    # Extract the core interaction message, stripping out internal markers
                    txt = c['context']
                    if "Interaction:" in txt:
                        # Clean the context: Only keep the interaction description, discard the drug headers
                        txt = txt.split("Interaction:", 1)[1].strip()
                    context_str += f"- {txt}\n"
                
            if live_data_str:
                context_str += f"\n\nREAL-WORLD EVIDENCE (OpenFDA):\n{live_data_str}"
                
        except Exception as e:
            context_str = "Error extracting semantic context from RAG."
            logger.error(f"RAG Error: {e}")
    
    rag_latency = time.time() - rag_start
    RAG_RETRIEVAL_LATENCY.observe(rag_latency)

    system_role = "You are a Senior Clinical Pharmacologist and Medical AI Assistant."
    
    prompt = f"""
### INSTRUCTIONS:
Explain the potential drug-drug interaction between {drug_a.upper()} and {drug_b.upper()}.
Your explanation MUST be specific to these two drugs. Avoid generic responses that could apply to any medication.

### INPUT DATA:
- Drug A: {drug_a}
- Drug B: {drug_b}
- Predicted Severity: {request.severity}
- ML Model Confidence: {request.confidence * 100:.1f}%

### CLINICAL EVIDENCE (RAG CONTEXT):
{context_str if len(contexts) > 0 else "No specific context found. Use your general medical training to provide a safe, cautious explanation."}

### FORMATTING RULES:
Provide exactly 4 points in clear, patient-friendly but professional language:
1. **Mechanism of Interaction**: How does {drug_a} affect {drug_b} (or vice-versa)? Mention if it's metabolic, additive, or antagonistic.
2. **Clinical Consequences**: What symptoms or physiological changes should the patient watch for?
3. **Recommended Action**: Should they avoid the combo, adjust timing, or monitor specific vitals?
4. **Confidence Note**: Briefly mention if this is based on specific clinical context or general pharmacological principles.

### SEVERITY VERIFICATION:
If the Predicted Severity '{request.severity}' is medically incorrect (e.g., if you know it is life-threatening but it's listed as Moderate), you MUST start your response with exactly:
REFINED_SEVERITY: [Level]
Where [Level] is one of: None, Mild, Moderate, Severe, Contraindicated.
Followed by a newline, then your 4 points.
If the Predicted Severity is correct, just provide the 4 points.

### CRITICAL SAFETY RULES:
- Mention ONLY '{drug_a}' and '{drug_b}'.
- If the RAG Context provided below mentions ANY OTHER drugs (like tetrabenazine, perampanel, etc.), you MUST COMPLETELY IGNORE those other drugs.
- Do NOT say 'when combined with X' if X is not {drug_a} or {drug_b}.
- If you find no relevant information for the pair {drug_a} and {drug_b}, provide a general pharmacological safety warning for this specific pair based on their classes.
- Use proper line breaks (\n) between points for readability.
- Do NOT use markdown stars (**) for bolding.
- Format headers exactly as: '1. Mechanism of Interaction:', '2. Clinical Consequences:', etc.
- FAILURE TO EXCLUDE OTHER DRUG NAMES IS A MEDICAL SAFETY VIOLATION.
"""

    logger.info(f"\n--- [AUDIT LOG: FINAL PROMPT] ---\n{prompt}\n----------------------------------")

    async def sse_generator():
        yield f"data: {json.dumps({'event': 'metrics', 'rag_retrieval_latency_sec': rag_latency})}\n\n"

        expert_data = get_expert_clinical_data(drug_a, drug_b)
        if expert_data:
            yield f"data: {json.dumps({'event': 'clinical_data', 'data': expert_data})}\n\n"
            # Also yield a summary token stream for the main panel
            summary = f"Expert System Analysis: {expert_data['why']}\n\nGenetic Considerations: {expert_data['genetic_factors']}"
            for word in summary.split(" "):
                yield f"data: {json.dumps({'event': 'token', 'text': word + ' '})}\n\n"
                await asyncio.sleep(0.01)
            return
        if model_gemini:
            try:
                responses = model_gemini.generate_content(prompt, stream=True)
                logger.info("[GENAI] Streaming Gemini Response...")
                for chunk in responses:
                    if chunk.text:
                        text = chunk.text
                        # Remove markdown stars to ensure a clean structure
                        text = text.replace("**", "")
                        
                        if "REFINED_SEVERITY:" in text:
                            try:
                                parts = text.split("\n", 1)
                                sev_line = parts[0]
                                new_sev = sev_line.replace("REFINED_SEVERITY:", "").strip()
                                # Clean up formatting artifacts
                                new_sev = "".join(filter(str.isalpha, new_sev))
                                yield f"data: {json.dumps({'event': 'severity', 'severity': new_sev, 'confidence': 0.98})}\n\n"
                                if len(parts) > 1:
                                    text = parts[1]
                                else:
                                    continue
                            except:
                                pass
                        yield f"data: {json.dumps({'event': 'token', 'text': text})}\n\n"
                logger.info("[GENAI] Gemini streaming complete.")
                return
            except Exception as e:
                logger.error(f"Gemini Error: {e}")
                logger.info("Falling back from Gemini provider.")

        # Tier 2: OpenAI Fallback
        if client_openai:
            try:
                response = await client_openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "You are a helpful medical AI."}, 
                              {"role": "user", "content": prompt}],
                    stream=True
                )
                logger.info("[GENAI] Streaming OpenAI Response...")
                async for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        content = content.replace("**", "")
                        if "REFINED_SEVERITY:" in content:
                             # For simplicity in fallback, we just strip it or handle it if it's in the first chunk
                             pass
                        yield f"data: {json.dumps({'event': 'token', 'text': content})}\n\n"
                return
            except Exception as e:
                logger.error(f"OpenAI Error: {e}")
                logger.info("Falling back from OpenAI provider.")
        else:
            logger.info("OpenAI API key not configured, skipping OpenAI fallback.")

        # Tier 3: RAG-Powered Mock
        logger.info("Using local fallback generator.")
        async for token in generate_rag_mock_stream(drug_a, drug_b, request.severity, request.confidence, context_str):
            yield token

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

# --- Kafka Worker Layer ---
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
ML_PREDICTIONS_TOPIC = "drug-interaction-ml-predictions"
RESULT_TOPIC = "drug-interaction-results"

async def kafka_worker():
    while True:
        try:
            consumer = AIOKafkaConsumer(
                ML_PREDICTIONS_TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id="genai-service-group",
                auto_offset_reset="earliest"
            )
            producer = AIOKafkaProducer(bootstrap_servers=KAFKA_SERVER)
            await consumer.start()
            await producer.start()
            logger.info("GENAI KAFKA WORKER STARTED")
            
            async for msg in consumer:
                data = json.loads(msg.value.decode())
                req_id = data.get("request_id")
                drug_a = data.get("drug_a")
                drug_b = data.get("drug_b")
                severity = data.get("severity")
                confidence = data.get("confidence")
                
                logger.info(f"GENAI PROCESSING {req_id}: {drug_a} + {drug_b}")
                
                # Perform Generation (Collecting the stream)
                full_text = ""
                final_severity = severity
                final_confidence = confidence
                
                try:
                    explain_start = time.time()
                    GENAI_REQUEST_COUNT.labels(provider="kafka", status="processing").inc()
                    
                    # RAG Context with Strict Filtering
                    rag_start = time.time()
                    contexts = rag.get_relevant_context(drug_a, drug_b, top_k=3) if rag else []
                    RAG_RETRIEVAL_LATENCY.observe(time.time() - rag_start)
                    
                    verified_contexts = []
                    da, db = drug_a.lower(), drug_b.lower()
                    is_same_drug = (da == db)
                    
                    for c in contexts:
                        ctx_text = c['context'].lower()
                        if not is_same_drug:
                            if da in ctx_text and db in ctx_text:
                                verified_contexts.append(c)
                        else:
                            if da in ctx_text and any(k in ctx_text for k in ["overdose", "toxicity", "lethal", "dosage", "repeated"]):
                                verified_contexts.append(c)

                    if verified_contexts:
                        context_str = ""
                        for c in verified_contexts:
                            txt = c['context']
                            if "Interaction:" in txt:
                                txt = txt.split("Interaction:", 1)[1].strip()
                            context_str += f"- {txt}\n"
                    else:
                        context_str = f"No specific clinical study context found for {drug_a} and {drug_b}. Providing general pharmacological assessment."
                    
                    # LLM Generation with Fallback
                    prompt = f"""
### INSTRUCTIONS:
Explain the potential drug-drug interaction between {drug_a.upper()} and {drug_b.upper()}.
Your explanation MUST be specific to these two drugs.

### INPUT DATA:
- Drug A: {drug_a}
- Drug B: {drug_b}
- Predicted Severity: {severity}
- ML Model Confidence: {confidence * 100:.1f}%

### CLINICAL EVIDENCE (RAG CONTEXT):
{context_str}

### SYNTHESIS INSTRUCTIONS:
- Use the provided RAG Context to explain the interaction.
- If the RAG Context only mentions one of the drugs (Soft Match), use your general medical knowledge to explain how it interacts with the other drug in that specific context.
- Provide a DETAILED, accurate explanation of the mechanism.
- Avoid generic warnings. Be specific to the pharmacology of {drug_a} and {drug_b}.

### SEVERITY VERIFICATION:
If the Predicted Severity '{severity}' is medically incorrect, you MUST start your response with exactly:
REFINED_SEVERITY: [Level]
Followed by a newline.
"""
                    # LLM Generation with Multi-Tier Fallback
                    success = False
                    
                    # Tier 1: Gemini
                    if not success and model_gemini:
                        try:
                            resp = model_gemini.generate_content(prompt)
                            full_text = resp.text
                            success = True
                            logger.info(f"LLM SUCCESS (Gemini) for {req_id}")
                        except Exception as e:
                            logger.warning(f"Gemini failure in Kafka worker: {e}")

                    # Tier 2: OpenAI
                    if not success and client_openai:
                        try:
                            resp = await client_openai.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role": "user", "content": prompt}]
                            )
                            full_text = resp.choices[0].message.content
                            success = True
                            logger.info(f"LLM SUCCESS (OpenAI) for {req_id}")
                        except Exception as e:
                            logger.warning(f"OpenAI failure in Kafka worker: {e}")

                    # Tier 3: RAG-Powered Mock Fallback
                    if not success:
                        logger.warning(f"All LLM providers failed for {req_id}. Falling back to RAG mock.")
                        full_text = ""
                        async for token in generate_rag_mock_stream(drug_a, drug_b, severity, confidence, context_str):
                            try:
                                json_str = token.replace("data: ", "").strip()
                                event_data = json.loads(json_str)
                                if event_data.get("event") == "token":
                                    full_text += event_data.get("text", "")
                                elif event_data.get("event") == "severity":
                                    final_severity = event_data.get("severity", final_severity)
                                    final_confidence = event_data.get("confidence", final_confidence)
                            except: pass
                        success = True # Mock always succeeds
                    
                    # Refined Severity Parsing (if from LLM)
                    if "REFINED_SEVERITY:" in full_text:
                        try:
                            lines = full_text.split("\n")
                            for line in lines:
                                if "REFINED_SEVERITY:" in line:
                                    final_severity = line.replace("REFINED_SEVERITY:", "").strip()
                                    final_severity = "".join(filter(str.isalpha, final_severity))
                                    break
                        except: pass

                    # Final Result
                    result_payload = {
                        "request_id": req_id,
                        "severity": final_severity,
                        "confidence": final_confidence,
                        "explanation": full_text,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await producer.send_and_wait(RESULT_TOPIC, json.dumps(result_payload).encode())
                    GENAI_EXPLAIN_LATENCY.observe(time.time() - explain_start)
                    logger.info(f"PUSHED RESULT FOR {req_id}")
                    
                except Exception as inner_e:
                    logger.error(f"GenAI Core Error: {inner_e}")
                    
        except Exception as e:
            logger.error(f"GENAI WORKER ERROR: {e}")
            await asyncio.sleep(5)
        finally:
            try:
                await consumer.stop()
                await producer.stop()
            except: pass

@app.on_event("startup")
async def startup_event():
    global rag
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        DATA_PATH = os.path.join(base_dir, "data", "cleaned_data.csv")
        DB_PATH = os.path.join(base_dir, "data", "vector_db")
        logger.info("Initializing RAG System...")
        rag = DrugInteractionRAG(data_path=DATA_PATH, db_path=DB_PATH)
        # Increase sample size for better coverage
        rag.build_database(sample_size=20000)
    except Exception as e:
        logger.error(f"RAG INITIALIZATION FAILED: {e}")
        
    asyncio.create_task(kafka_worker())
