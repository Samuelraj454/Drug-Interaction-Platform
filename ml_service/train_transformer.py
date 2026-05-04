import pandas as pd
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from datasets import Dataset
import os

# --- Constants ---
MODEL_NAME = "dmis-lab/biobert-v1.1" # BioBERT
DATA_PATH = "d:/drug-interaction-platform/data-pipeline/dataset2.csv"
OUTPUT_DIR = "d:/drug-interaction-platform/data/transformer_model"
LABELS = ["None", "Mild", "Moderate", "Severe", "Contraindicated"]
LABEL_MAP = {l: i for i, l in enumerate(LABELS)}

def preprocess_data():
    df = pd.read_csv(DATA_PATH)
    
    def map_severity(row):
        sev = row['severity'].lower()
        effect = str(row['effect']).lower()
        rationale = str(row['rationale']).lower()
        
        if "contraindicated" in effect or "contraindicated" in rationale:
            return "Contraindicated"
        if sev == "major":
            return "Severe"
        if sev == "moderate":
            return "Moderate"
        if sev == "minor":
            return "Mild"
        return "Mild" # Default fallback for interactions

    df['label_str'] = df.apply(map_severity, axis=1)
    df['text'] = df['drug_a'] + " [SEP] " + df['drug_b'] + " [SEP] " + df['mechanism']
    
    # Add negative samples (None)
    # Since we have only 182 positive rows, let's add some negatives
    # In a real system we'd use random pairs, but here we'll mock some
    none_data = [
        {"drug_a": "Aspirin", "drug_b": "Vitamin C", "text": "Aspirin [SEP] Vitamin C [SEP] No known interaction", "label_str": "None"},
        {"drug_a": "Loratadine", "drug_b": "Paracetamol", "text": "Loratadine [SEP] Paracetamol [SEP] Safe combination", "label_str": "None"},
    ]
    df_none = pd.DataFrame(none_data)
    df = pd.concat([df, df_none], ignore_index=True)
    
    df['label'] = df['label_str'].map(LABEL_MAP)
    return df[['text', 'label']]

def train():
    df = preprocess_data()
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    
    def tokenize(batch):
        return tokenizer(batch['text'], padding='max_length', truncation=True, max_length=128)
    
    train_dataset = Dataset.from_pandas(train_df).map(tokenize, batched=True)
    test_dataset = Dataset.from_pandas(test_df).map(tokenize, batched=True)
    
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=len(LABELS))
    
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        evaluation_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=8,
        num_train_epochs=3,
        weight_decay=0.01,
        logging_dir='./logs',
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
    )
    
    print("Starting training...")
    trainer.train()
    
    print(f"Saving model to {OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    train()
