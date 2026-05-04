import pandas as pd
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
import uuid

class DrugInteractionRAG:
    def __init__(self, data_path, db_path):
        self.data_path = data_path
        self.db_path = db_path
        
        print("Initializing ChromaDB...")
        os.makedirs(self.db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.db_path)
        
        print("Loading sentence-transformer model (all-MiniLM-L6-v2)...")
        # all-MiniLM-L6-v2 is an extremely efficient model for embedding generic sentences/queries
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.collection = self.client.get_or_create_collection(name="drug_interactions")
        
    def build_database(self, sample_size=5000):
        if self.collection.count() > 0:
            print(f"Collection 'drug_interactions' already contains {self.collection.count()} items. Skipping generation.")
            return

        print(f"Loading data from {self.data_path}...")
        df = pd.read_csv(self.data_path)
        
        # Only index actual interactions (label == 1)
        if 'label' in df.columns:
            df = df[df['label'] == 1]
            
        print(f"Total authentic interactions: {len(df)}")
        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)
            
        print(f"Preparing {len(df)} documents for Vector DB...")
        
        documents = []
        metadatas = []
        ids = []
        
        for idx, row in df.iterrows():
            drug_a = str(row['drug_a']).lower()
            drug_b = str(row['drug_b']).lower()
            text = str(row['text'])
            
            doc_text = f"Drug A: {drug_a} | Drug B: {drug_b} | Interaction: {text}"
            documents.append(doc_text)
            ids.append(str(uuid.uuid4()))
            metadatas.append({
                "drug_a": drug_a,
                "drug_b": drug_b,
                "source": "drug-interaction-schema"
            })
            
        print(f"Generating embeddings for {len(documents)} elements...")
        embeddings = self.embedding_model.encode(documents, show_progress_bar=False).tolist()
        
        print("Inserting into Vector Database...")
        batch_size = 5000 # Chroma allows up to ~5461 by default depending on config
        for i in range(0, len(documents), batch_size):
            end = i + batch_size
            self.collection.add(
                documents=documents[i:end],
                embeddings=embeddings[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end]
            )
            
        print("Vector database completely ingested and persisted.")

    def get_relevant_context(self, drug_a, drug_b, top_k=3, threshold=1.3):
        drug_a, drug_b = drug_a.lower().strip(), drug_b.lower().strip()
        query = f"interaction between {drug_a} and {drug_b}"
        
        print(f"\n[RAG] Querying for: '{query}'")
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )
        
        returned_docs = results['documents'][0]
        returned_metas = results['metadatas'][0]
        returned_distances = results['distances'][0]
        
        # Deduplication and Thresholding
        unique_contexts = []
        seen = set()
        
        print(f"[RAG] Found {len(returned_docs)} potential matches.")
        
        for doc, meta, dist in zip(returned_docs, returned_metas, returned_distances):
            if doc not in seen:
                seen.add(doc)
                
                # IDENTITY CHECK: Ensure at least one of the input drugs matches the metadata
                # This prevents "Hallucinating" different drugs in the explanation
                meta_a = str(meta.get("drug_a", "")).lower()
                meta_b = str(meta.get("drug_b", "")).lower()
                
                # We expect either (A==metaA AND B==metaB) OR (A==metaB AND B==metaA)
                if drug_a == drug_b:
                    # If same drug, both meta_a and meta_b must be that drug (self-interaction)
                    is_identity_match = (meta_a == drug_a and meta_b == drug_a)
                else:
                    # If different drugs, both must be present in the metadata
                    is_identity_match = (drug_a in [meta_a, meta_b]) and (drug_b in [meta_a, meta_b])
                
                # RELEVANCE CHECK
                is_relevant = dist < threshold and is_identity_match
                status = "✅ RELEVANT" if is_relevant else ("❌ IDENTITY MISMATCH" if not is_identity_match else "❌ TOO DISTANT")
                
                print(f"  - [{status}] Dist: {round(dist, 4)} | Doc: {doc[:100]}...")
                
                if is_relevant:
                    unique_contexts.append({
                        "context": doc,
                        "drug_a": meta_a,
                        "drug_b": meta_b,
                        "distance_score": round(dist, 4)
                    })
        
        print(f"[RAG] Final context count after thresholding: {len(unique_contexts)}")
        return unique_contexts

if __name__ == "__main__":
    DATA_PATH = "d:/drug-interaction-platform/data/cleaned_data.csv"
    DB_PATH = "d:/drug-interaction-platform/data/vector_db"
    
    rag = DrugInteractionRAG(data_path=DATA_PATH, db_path=DB_PATH)
    
    # Phase 1-4: Build / Ingest the database
    rag.build_database(sample_size=3000)
    
    # Phase 5-7: Retrieve and Test
    test_drug_a = "aspirin"
    test_drug_b = "warfarin"
    
    print(f"\n--- TESTING RETRIEVAL for {test_drug_a.upper()} and {test_drug_b.upper()} ---")
    context_results = rag.get_relevant_context(test_drug_a, test_drug_b, top_k=5)
    
    for i, res in enumerate(context_results):
        print(f"\n[Result {i+1} | Score: {res['distance_score']}]")
        print(res['context'])
