import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
import os

# PHASE 1 - LOAD & INSPECT
print("\n--- PHASE 1: LOAD & INSPECT DATASET ---")
dataset_path = 'd:/drug-interaction-platform/data-pipeline/dataset1.csv'
df_raw = pd.read_csv(dataset_path)

print("Shape:", df_raw.shape)
print("Columns:", df_raw.columns.tolist())
print("Null values:\n", df_raw.isnull().sum())
print("\nSample rows:\n", df_raw.head(2))

# PHASE 2 - DATA CLEANING
print("\n--- PHASE 2: DATA CLEANING ---")
# Rename to standard schema
df = df_raw.rename(columns={
    'Drug 1': 'drug_a', 
    'Drug 2': 'drug_b', 
    'Interaction Description': 'text'
})

# All entries in dataset1 describe positive interactions
df['label'] = 1

# Handle missing values
df = df.dropna(subset=['drug_a', 'drug_b', 'text'])

# Normalize drug names
df['drug_a'] = df['drug_a'].astype(str).str.lower().str.strip()
df['drug_b'] = df['drug_b'].astype(str).str.lower().str.strip()

# Remove duplicates
df = df.drop_duplicates(subset=['drug_a', 'drug_b'])

# Generate Negative Samples to make it a real ML problem (label 0)
print("Generating negative samples for label variance...")
unique_drugs = pd.concat([df['drug_a'], df['drug_b']]).unique()
np.random.seed(42)
neg_a = np.random.choice(unique_drugs, size=50000)
neg_b = np.random.choice(unique_drugs, size=50000)
# Create negative dataframe
neg_df = pd.DataFrame({
    'drug_a': neg_a, 
    'drug_b': neg_b, 
    'text': 'no interaction known or reported', 
    'label': 0
})

df = pd.concat([df, neg_df]).sample(frac=1, random_state=42).reset_index(drop=True)

# Select standardized schema
df = df[['drug_a', 'drug_b', 'text', 'label']]

print("Cleaned Dataset Shape:", df.shape)
print("Cleaned Labels Distribution:\n", df['label'].value_counts())

# PHASE 3 - FEATURE ENGINEERING
print("\n--- PHASE 3: FEATURE ENGINEERING ---")
# 1. Basic features
df['text_length'] = df['text'].apply(len)

# Drug pair frequency (frequency of individual drugs acting in pairs)
drug_a_counts = df['drug_a'].value_counts()
drug_b_counts = df['drug_b'].value_counts()
df['freq_drug_a'] = df['drug_a'].map(drug_a_counts)
df['freq_drug_b'] = df['drug_b'].map(drug_b_counts)

# In order to manage memory/speed effectively on local environment, subsetting to 30,000 samples if larger
df_final = df.head(30000).copy()

# 2. Text Features (TF-IDF)
print("Generating TF-IDF features...")
tfidf = TfidfVectorizer(max_features=100)
X_text = tfidf.fit_transform(df_final['text']).toarray()

# 3. Combine into feature matrix X
X_basic = df_final[['text_length', 'freq_drug_a', 'freq_drug_b']].values
X = np.hstack([X_basic, X_text])

# 4. Prepare labels y
y = df_final['label'].values

print("Feature Matrix X shape:", X.shape)
print("Labels y shape:", y.shape)

# PHASE 4 - TRAIN/TEST SPLIT
print("\n--- PHASE 4: TRAIN/TEST SPLIT ---")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print("X_train shape:", X_train.shape)
print("X_test shape:", X_test.shape)

# PHASE 5 - SAVE ARTIFACTS
print("\n--- PHASE 5: SAVE ARTIFACTS ---")
output_dir = 'd:/drug-interaction-platform/data'
os.makedirs(output_dir, exist_ok=True)

df_final.to_csv(os.path.join(output_dir, 'cleaned_data.csv'), index=False)
np.save(os.path.join(output_dir, 'features.npy'), X)
np.save(os.path.join(output_dir, 'labels.npy'), y)
print("Saved artifacts to d:/drug-interaction-platform/data/")

# PHASE 6 - VALIDATION
print("\n--- PHASE 6: VALIDATION ---")
assert not np.isnan(X).any(), "Error: NaNs found in feature matrix!"
assert X.shape[0] == y.shape[0], "Error: Shapes of X and y do not match!"
assert len(np.unique(y)) > 1, "Error: Only one class found in labels!"

print("Validation passed. ")
print("Dataset is FULLY processed, ML-ready, and saved!")
