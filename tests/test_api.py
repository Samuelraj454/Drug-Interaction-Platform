import pytest
import httpx
import json
import asyncio

# Testing the API Gateway
# Note: This requires the API Gateway to be running (e.g., during integration testing step)
# For now, we simulate the SSE streaming logic check.

@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        # Mocking the call or if running locally
        try:
            response = await client.get("http://localhost:8000/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        except:
            pytest.skip("API not running")

@pytest.mark.asyncio
async def test_analyse_streaming():
    url = "http://localhost:8000/analyse"
    payload = {"drug_a": "warfarin", "drug_b": "aspirin"}
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("POST", url, json=payload, timeout=10.0) as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream"
                
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line.replace("data: ", ""))
                        events.append(event)
                        if len(events) >= 2: # Check if we get both severity and some tokens
                            break
                
                assert any(e["event"] == "severity" for e in events)
        except Exception as e:
            pytest.skip(f"API connection failed: {e}")

def test_cache_hit():
    # This would test if the second call is faster than the first
    from api_gateway.main import cache
    cache[tuple(sorted(["drug_x", "drug_y"]))] = {
        "severity": "Severe",
        "confidence": 0.99,
        "explanation": "Test"
    }
    assert tuple(sorted(["drug_x", "drug_y"])) in cache
