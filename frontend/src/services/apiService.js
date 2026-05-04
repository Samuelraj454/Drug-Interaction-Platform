/**
 * API Service for Drug Interaction Intelligence
 * Handles POST-based SSE streaming using fetch + ReadableStream
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export async function analyzeInteraction(drugA, drugB, onEvent, onError) {
  try {
    const response = await fetch(`${API_BASE_URL}/analyse`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        drug_a: drugA,
        drug_b: drugB,
        text: "" // Optional additional context
      }),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split by double newline (SSE standard)
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // Keep partial line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const jsonStr = line.replace("data: ", "").trim();
            if (jsonStr) {
              const data = JSON.parse(jsonStr);
              onEvent(data);
            }
          } catch (e) {
            console.error("Error parsing SSE JSON:", e, line);
          }
        }
      }
    }
  } catch (error) {
    console.error("Fetch/Streaming error:", error);
    onError(error.message);
  }
}

export async function fetchHistory() {
  try {
    const response = await fetch(`${API_BASE_URL}/history`);
    if (!response.ok) throw new Error("Failed to fetch history");
    return await response.json();
  } catch (err) {
    console.error("Error fetching history:", err);
    return [];
  }
}
export async function fetchSystemStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/metrics/summary`);
    if (!response.ok) throw new Error("Failed to fetch metrics");
    return await response.json();
  } catch (err) {
    console.error("Error fetching system stats:", err);
    return null;
  }
}
