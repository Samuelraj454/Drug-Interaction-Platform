import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
import os

def rebuild_artifacts():
    print("Rebuilding preprocessing artifacts...")
    dataset_path = 'd:/drug-interaction-platform/data-pipeline/dataset1.csv'
    
    # Load data
    df_raw = pd.read_csv(dataset_path)
    
    # Clean
    df = df_raw.rename(columns={
        'Drug 1': 'drug_a', 
        'Drug 2': 'drug_b', 
        'Interaction Description': 'text'
    })
    df = df.dropna(subset=['drug_a', 'drug_b', 'text'])
    df['drug_a'] = df['drug_a'].astype(str).str.lower().str.strip()
    df['drug_b'] = df['drug_b'].astype(str).str.lower().str.strip()
    df = df.drop_duplicates(subset=['drug_a', 'drug_b'])
    
    # Generate Negatives
    unique_drugs = pd.concat([df['drug_a'], df['drug_b']]).unique()
    np.random.seed(42)
    neg_a = np.random.choice(unique_drugs, size=50000)
    neg_b = np.random.choice(unique_drugs, size=50000)
    neg_df = pd.DataFrame({
        'drug_a': neg_a, 
        'drug_b': neg_b, 
        'text': 'no interaction known or reported', 
        'label': 0
    })
    
    df = pd.concat([df, neg_df]).sample(frac=1, random_state=42).reset_index(drop=True)
    df = df[['drug_a', 'drug_b', 'text', 'label']]
    
    # Text TF-IDF
    df_final = df.head(30000).copy()
    
    # Combine frequency counts from the final sampled data that matched training
    drug_counts = pd.concat([df_final['drug_a'], df_final['drug_b']]).value_counts().to_dict()
    
    tfidf = TfidfVectorizer(max_features=100)
    tfidf.fit(df_final['text'])
    
    # Save artifacts
    output_dir = 'd:/drug-interaction-platform/data'
    os.makedirs(output_dir, exist_ok=True)
    
    joblib.dump(tfidf, os.path.join(output_dir, 'tfidf.joblib'))
    joblib.dump(drug_counts, os.path.join(output_dir, 'drug_counts.joblib'))
    print("Artifacts rebuilt and persisted.")

if __name__ == "__main__":
    rebuild_artifacts()
