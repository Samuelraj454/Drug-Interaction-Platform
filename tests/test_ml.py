import pytest
import os
import joblib
import numpy as np

# We'll mock the prediction logic since we don't want to load actual models during unit testing if possible,
# or we can test if the model structure is as expected.

def test_data_artifacts_exist():
    data_dir = "d:/drug-interaction-platform/data"
    assert os.path.exists(os.path.join(data_dir, "model.joblib"))
    assert os.path.exists(os.path.join(data_dir, "tfidf.joblib"))

def test_model_prediction_schema():
    # Simple test for feature dimensions
    data_dir = "d:/drug-interaction-platform/data"
    tfidf = joblib.load(os.path.join(data_dir, "tfidf.joblib"))
    model = joblib.load(os.path.join(data_dir, "model.joblib"))
    
    # 3 basic features + tfidf features
    expected_dim = 3 + len(tfidf.get_feature_names_out())
    assert model.n_features_in_ == expected_dim

def test_rag_retrieval_logic():
    # Mock retrieval logic check
    from genai_service.rag_pipeline import DrugInteractionRAG
    DATA_PATH = "d:/drug-interaction-platform/data/cleaned_data.csv"
    DB_PATH = "d:/drug-interaction-platform/data/vector_db"
    
    if os.path.exists(DATA_PATH) and os.path.exists(DB_PATH):
        rag = DrugInteractionRAG(DATA_PATH, DB_PATH)
        res = rag.get_relevant_context("aspirin", "warfarin")
        assert isinstance(res, list)
