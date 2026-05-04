import os
import pandas as pd
import numpy as np
import torch
import sqlite3
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
DATA_DIR = "d:/drug-interaction-platform/data"
DB_PATH = "d:/drug-interaction-platform/data/history.db"
MODEL_NAME = "emilyalsentzer/Bio_ClinicalBERT"
OUTPUT_DIR = os.path.join(DATA_DIR, "transformer_model")
BATCH_SIZE = 4 # Even smaller for BioBERT on CPU
EPOCHS = 1 

# --- CLASS WEIGHTS (Computed for Imbalance) ---
# Weights: [None, Mild, Moderate, Severe, Contraindicated]
CLASS_WEIGHTS = torch.tensor([1.0, 1.0, 1.2, 5.0, 10.0])

# Mapping: None: 0, Mild: 1, Moderate: 2, Severe: 3, Contraindicated: 4
SEVERITY_MAP = {
    "None": 0,
    "Mild": 1,
    "Moderate": 2,
    "Severe": 3,
    "Contraindicated": 4
}

def extract_severity_heuristic(text):
    text = text.lower()
    
    # LEVEL 4: CONTRAINDICATED (Highest risk)
    # Adding more specific critical terms
    critical_keywords = [
        "contraindicated", "fatal", "lethal", "life-threatening", "unacceptable risk", 
        "must not", "death", "anaphylaxis", "stevens-johnson syndrome", "toxic epidermal necrolysis",
        "cardiac arrest", "respiratory arrest", "severe hemorrhage"
    ]
    if any(k in text for k in critical_keywords):
        return 4 
        
    # LEVEL 3: SEVERE (Significant clinical danger)
    # Expanding with more serious adverse clinical events
    severe_keywords = [
        "risk or severity of adverse effects can be increased", 
        "major risk", "severe", "serious", "qtc-prolonging", "anticoagulant effect", 
        "hypotensive", "hypoglycemic", "respiratory depression", "renal failure", "heart block",
        "serotonin syndrome", "rhabdomyolysis", "neutropenia", "thrombocytopenia", "angioedema"
    ]
    if any(k in text for k in severe_keywords):
        return 3 
        
    # LEVEL 2: MODERATE (Clinically significant, requires monitoring)
    # Adding pharmaceutical activity keywords
    moderate_keywords = [
        "metabolism", "serum concentration", "bioavailability", "clearance", "moderate",
        "inhibit", "induce", "enzyme", "substrate", "cyp3a4", "p-glycoprotein",
        "absorption", "excretion", "pharmacokinetics"
    ]
    if any(k in text for k in moderate_keywords):
        # Prioritize 'Increased' as a marker of potential toxicity
        if "increased" in text or "decreased" in text or "moderate" in text:
            return 2
        return 2 
        
    # LEVEL 1: MILD (Minimal clinical significance)
    if any(k in text for k in ["minor", "mild", "insignificant", "slight", "minimal"]):
        return 1
        
    # DEFAULT for identified interaction
    return 1 

def load_data():
    # 1. Load base cleaned data
    df = pd.read_csv(os.path.join(DATA_DIR, 'cleaned_data.csv'))
    
    # 2. Map binary labels to multi-class using text heuristic
    df['mapped_label'] = df.apply(lambda row: extract_severity_heuristic(row['text']) if row['label'] == 1 else 0, axis=1)
    
    logger.info("Class distribution after heuristic:")
    logger.info(df['mapped_label'].value_counts().to_dict())
    
    # 3. Load corrections from DB if exists
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            corr_df = pd.read_sql_query("SELECT drug_a, drug_b, severity FROM corrections", conn)
            conn.close()
            
            if not corr_df.empty:
                logger.info(f"Loaded {len(corr_df)} corrections from database.")
                # We need to find the descriptions for these corrections or just synthetic ones
                # For now, we mix them in. In a real system, we'd join with history.
                # Here we just add them as extra weighted samples
                corr_df['text'] = corr_df.apply(lambda x: f"Interaction between {x['drug_a']} and {x['drug_b']}", axis=1)
                corr_df['mapped_label'] = corr_df['severity'].map(SEVERITY_MAP).fillna(2).astype(int)
                
                df = pd.concat([df[['text', 'mapped_label']], corr_df[['text', 'mapped_label']]], ignore_index=True)
        except Exception as e:
            logger.warning(f"Could not load corrections: {e}")

    return df[['text', 'mapped_label']]

class DrugDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item['labels'] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    f1 = f1_score(labels, preds, average='weighted')
    acc = accuracy_score(labels, preds)
    return {
        'accuracy': acc,
        'f1': f1,
    }

class WeightedTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        
        # Use Weighted Loss
        loss_fct = torch.nn.CrossEntropyLoss(weight=CLASS_WEIGHTS.to(model.device))
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss

def main():
    logger.info(f"Starting BioBERT ({MODEL_NAME}) Retraining Pipeline...")
    
    # Check for CPU/GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    df = load_data()
    
    # Limit data for CPU demo if too large, but keep it representative
    if device == "cpu" and len(df) > 2000:
        logger.info("CPU detected. Downsampling to 2000 for BioBERT feasibility.")
        df = df.sample(2000, random_state=42)

    X_train, X_val, y_train, y_val = train_test_split(
        df['text'].tolist(), 
        df['mapped_label'].tolist(), 
        test_size=0.1, 
        random_state=42,
        stratify=df['mapped_label']
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    train_encodings = tokenizer(X_train, truncation=True, padding=True, max_length=128)
    val_encodings = tokenizer(X_val, truncation=True, padding=True, max_length=128)

    train_dataset = DrugDataset(train_encodings, y_train)
    val_dataset = DrugDataset(val_encodings, y_val)

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=5)

    training_args = TrainingArguments(
        output_dir='./results',
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        warmup_steps=50,
        weight_decay=0.01,
        logging_dir='./logs',
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=20,
        save_strategy="no",
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    logger.info("Beginning BioBERT Training...")
    trainer.train()
    
    logger.info(f"Saving model to {OUTPUT_DIR}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info("Retraining Complete!")

if __name__ == "__main__":
    main()
