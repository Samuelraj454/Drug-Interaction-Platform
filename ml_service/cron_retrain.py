import sqlite3
import subprocess
import time
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "d:/drug-interaction-platform/data/history.db"
RETRAIN_SCRIPT = "d:/drug-interaction-platform/ml_service/retrain_pipeline.py"
THRESHOLD = 50 # Retrain every 50 new corrections

def count_corrections():
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM corrections")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Error counting corrections: {e}")
        return 0

def main():
    logger.info("Starting Retraining Monitor...")
    last_count = count_corrections()
    
    while True:
        # Check every hour or suitable interval
        time.sleep(3600) 
        
        current_count = count_corrections()
        logger.info(f"Monitor check: {current_count} corrections found.")
        
        if current_count >= last_count + THRESHOLD:
            logger.info(f"Threshold met ({current_count} >= {last_count} + {THRESHOLD}). Triggering retraining...")
            try:
                # Trigger retraining pipeline
                subprocess.run(["python", RETRAIN_SCRIPT], check=True)
                last_count = current_count
                logger.info("Scheduled retraining complete.")
            except Exception as e:
                logger.error(f"Scheduled retraining failed: {e}")

if __name__ == "__main__":
    main()
