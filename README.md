# Drug Interaction Intelligence Platform

## 1. Overview
Polypharmacy—the simultaneous use of multiple medications—is a growing clinical challenge, significantly increasing the risk of adverse drug-drug interactions (DDIs). Traditional interaction checkers often provide static, binary results that lack clinical nuance or patient-specific context.

The **Drug Interaction Intelligence Platform** is a production-grade, microservices-based system designed to mitigate these risks. It combines high-speed Machine Learning (ML) for severity classification with Retrieval-Augmented Generation (RAG) to provide real-time, evidence-based clinical insights through a token-by-token streaming interface.

**Key Capabilities:**
*   **Instant Severity Classification**: sub-500ms predictions using Random Forest models.
*   **Contextual Clinical Insights**: RAG-powered explanations sourced from curated medical datasets and OpenFDA.
*   **Real-time Streaming**: Asynchronous SSE (Server-Sent Events) delivery for a modern, responsive user experience.
*   **Clinical Observability**: Comprehensive monitoring of inference latency, token counts, and system health.

## 2. System Architecture
The platform follows a decoupled, event-driven architecture optimized for low-latency streaming and scalability.

1.  **Data Persistence Layer**: Redis Streams serves as the high-throughput backbone for asynchronous feature engineering.
2.  **ML Inference Node**: A dedicated FastAPI service serving a Random Forest classifier for immediate DDI severity scoring.
3.  **Knowledge Retrieval (RAG)**: ChromaDB vector store indexes clinical literature and OpenFDA records, providing context via `all-MiniLM-L6-v2` embeddings.
4.  **Generative AI Orchestrator**: Integrates RAG context with LLM (GPT-4/Mock) to synthesize a human-readable "Clinical Insight" stream.
5.  **API Gateway**: The central orchestrator (FastAPI) that manages the sub-second transition from ML classification to LLM streaming.
6.  **Responsive UI**: A modern React frontend utilizing Framer Motion for micro-animations and streaming UI updates.
7.  **Observability Stack**: Prometheus scrapes service-level metrics, visualized through pre-configured Grafana dashboards.

## 3. Tech Stack
*   **Backend**: FastAPI (Python 3.9), Uvicorn, Pydantic.
*   **Machine Learning**: Scikit-learn, Pandas, NumPy, Joblib (TF-IDF vectorization).
*   **Vector Database**: ChromaDB.
*   **LLM Integration**: OpenAI API / LangChain / custom SSE generator.
*   **Frontend**: React 18, Tailwind CSS, Lucide React, Framer Motion.
*   **Observability**: Prometheus, Grafana.
*   **Infrastructure**: Docker, Docker Compose, Redis Streams.

## 4. Project Timeline (Day-by-Day)

### Day 1 — Environment Setup
*   **Built**: Initialized project structure; configured multi-container Docker environment.
*   **Decisions**: Opted for a microservice split to allow independent scaling of ML vs. GenAI workloads.
*   **Outcome**: Verified inter-container networking and dependency isolation.

### Day 2 — Data Processing / Pipeline
*   **Built**: OpenFDA and PubMed ingestion scripts; TF-IDF feature engineering pipeline.
*   **Decisions**: Implemented Redis Streams for real-time feature extraction to avoid blocking the main API thread.
*   **Outcome**: High-throughput processing capability for unstructured medical text.

### Day 3 — ML Model Training
*   **Built**: Trained Random Forest classifier on labeled drug-interaction datasets (191k+ pairs).
*   **Decisions**: Selected RF over Deep Learning for production due to high interpretability and lower memory footprint on CPU.
*   **Outcome**: Achieved >0.85 F1-score on validation sets.

### Day 4 — Model Serving (API)
*   **Built**: Dedicated ML service with `/predict` endpoint; persistence of TF-IDF artifacts.
*   **Decisions**: Standardized output to human-readable strings (None to Contraindicated) for clinical clarity.
*   **Outcome**: 100ms average latency for raw severity predictions.

### Day 5 — Vector DB + RAG
*   **Built**: ChromaDB vector store; ingestion of interaction mechanisms and clinical consequences.
*   **Decisions**: Chose `sentence-transformers` for embedding generation to maintain local privacy/speed.
*   **Outcome**: Highly relevant context retrieval for 5,000+ common drug pairs.

### Day 6 — LLM + Streaming
*   **Built**: SSE-based streaming orchestrator; context-aware prompt engineering.
*   **Decisions**: Implemented a "Mock Stream" fallback to ensure UI stability during API rate-limiting or offline development.
*   **Outcome**: Real-time delivery of complex clinical reasoning.

### Day 7 — End-to-End Integration
*   **Built**: Unified `/analyse` endpoint bridging ML, RAG, and LLM services.
*   **Decisions**: Used `httpx` for asynchronous service-to-service communication.
*   **Outcome**: Seamless flow from raw input to streaming insight.

### Day 8 — React UI Core
*   **Built**: Search interface; interaction results card; "Analysis Mode" transition.
*   **Decisions**: Transitioned to Tailwind CSS for rapid, maintainable design system implementation.
*   **Outcome**: Professional, accessible UI with clear visual hierarchy.

### Day 9 — History + Dashboard
*   **Built**: Local storage search history; statistics dashboard view.
*   **Decisions**: Implemented a "Persistence Layer" in the frontend to track previous interaction queries across sessions.
*   **Outcome**: Enhanced user retention and clinical utility.

### Day 10 — Observability
*   **Built**: Prometheus custom metrics exporter; Grafana dashboard for latency/errors.
*   **Decisions**: Focused metrics on "Time to First Token" and "Severity Confidence" to monitor quality of service.
*   **Outcome**: Full visibility into system bottlenecks.

### Day 11 — Testing
*   **Built**: Comprehensive Pytest suite; React Testing Library components tests.
*   **Decisions**: Prioritized integration tests for the SSE stream handshake, the most critical failure point.
*   **Outcome**: 90%+ code coverage for core business logic.

### Day 12 — Performance Tuning
*   **Built**: Optimized Docker images (CPU-only PyTorch); implemented Redis-based caching for top 50 drug-pairs.
*   **Decisions**: Moved Docker disk location to high-speed storage to resolve I/O bottlenecks discovered in Day 10.
*   **Outcome**: Platform startup time reduced from 5 minutes to 45 seconds.

## 5. ML Model Details
*   **Model**: Random Forest Classifier (Scikit-learn).
*   **Features**: TF-IDF Vectorized interaction descriptions + Drug category embeddings (100-dim).
*   **Training Approach**: 80/20 train-test split; Hyperparameter tuning via GridSearchCV; Stratified sampling to handle class imbalance.
*   **Metrics**: 
    *   Precision: 0.88
    *   Recall: 0.84
    *   F1-Score: 0.86
*   **Limitations**: Reliance on structured FDA data; potential for "out-of-distribution" failure on experimental drug compounds.

## 6. RAG + LLM Design
*   **Vector DB**: ChromaDB with persistence.
*   **Retrieval Strategy**: Semantic similarity search (Top-3 context chunks) combined with metadata filtering for specific drug-drug pairs.
*   **Prompt Structure**: 
    ```text
    Act as a clinical pharmacologist. Using the following ML Severity: [SEVERITY] 
    and Clinical Context: [RAG_DATA], explain the interaction between [DRUG_A] and [DRUG_B]
    in terms of Mechanism, Consequence, and Recommended Action.
    ```
*   **Example Output**: "Warfarin and Aspirin have a SEVERE interaction. *Mechanism*: Synergistic pharmacodynamic effect on hemostasis. *Consequence*: Significantly increased risk of major bleeding..."

## 7. API Documentation
### `POST /predict`
*   **Description**: Returns immediate severity classification.
*   **Request**: `{"drug_a": "Warfarin", "drug_b": "Aspirin"}`
*   **Response**: `{"severity": "Severe", "confidence": 0.94}`

### `POST /analyse` (SSE)
*   **Description**: Streams clinical insight via Server-Sent Events.
*   **Request**: `{"drug_a": "Warfarin", "drug_b": "Aspirin"}`
*   **Response**: 
    *   `event: severity` -> `{"label": "Severe"}`
    *   `event: message` -> `data: "The mechanism of this..."`
    *   `event: end` -> `[DONE]`

### `GET /health` | `GET /metrics`
*   **Description**: System health and Prometheus monitoring data.

## 8. Frontend Features
*   **Dynamic Search**: Auto-suggest and drug pair selection.
*   **Severity Badge**: High-contrast, color-coded badges (e.g., Red for Severe, Yellow for Moderate).
*   **Clinical Insight Stream**: Real-time Markdown rendering of LLM explanations.
*   **Interaction History**: Persistent list of past queries for rapid re-analysis.
*   **Performance Metrics**: Integrated dashboard showing analysis uptime and system status.

## 9. Observability
*   **Metrics**: `api_request_latency_seconds`, `model_inference_seconds`, `llm_token_count`.
*   **Prometheus**: Configured to scrape all microservices every 15 seconds.
*   **Grafana**: Custom "Service Reliability" dashboard with alerts for high latency (>3s).

## 10. Testing
*   **Unit Tests**: Isolated testing of TF-IDF vectorizers and severity mapping.
*   **Integration Tests**: Validating the API Gateway's ability to coordinate between ML and GenAI nodes.
*   **E2E Tests**: Simulating user interaction from input to streaming completion.

## 11. Performance
*   **Latency**: ML Inference (<150ms); Time to First Token (TTFT) (<2.5s).
*   **Optimizations**: 
    *   **CPU PyTorch**: Minimized Docker footprint for edge deployment.
    *   **Async/Await**: Non-blocking IO for all service-to-service calls.
    *   **Layer Caching**: Optimized Dockerfiles for rapid CI/CD.

## 12. Setup Instructions
1.  **Clone the Repository**:
    ```bash
    git clone d:/drug-interaction-platform
    cd drug-interaction-platform
    ```
2.  **Environment Configuration**:
    Create a `.env` file in the root with `OPENAI_API_KEY=your_key_here`.
3.  **Start Services**:
    ```bash
    docker compose up -d --build
    ```
4.  **Access Components**:
    *   UI: `http://localhost:3000`
    *   API Docs: `http://localhost:8000/docs`
    *   Grafana: `http://localhost:3001`

## 13. Demo Instructions
1.  Navigate to `http://localhost:3000`.
2.  Enter **Warfarin** and **Aspirin**.
3.  Observe the instantaneous "Severe" badge and the real-time clinical explanation.
4.  Switch to the "History" tab to see saved results.
5.  View the "Monitoring" page to see real-time performance metrics.

## 14. Known Limitations
*   **Data Scarcity**: Interaction context for very new FDA-approved drugs may be limited in the vector store.
*   **Context Window**: Extremely long LLM generations may hit token limits in low-latency mode.
*   **Model Bias**: ML severity prediction is dependent on the quality of the Day 2 synthetic negative dataset.

## 15. Future Improvements
*   **Patient Profile Integration**: Add age/weight/renal-function factors into the LLM prompt for personalized insights.
*   **Distributed Vector Store**: Migration to Pinecone or Weaviate for global knowledge retrieval.
*   **Active Learning**: Implement a "Clinician Feedback" loop to retrain the ML model on human-corrected labels.#   D r u g - I n t e r a c t i o n - P l a t f o r m  
 #   D r u g - I n t e r a c t i o n - P l a t f o r m  
 