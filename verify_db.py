import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("personal_metric.db")

def verify():
    if not DB_PATH.exists():
        print("Database not found!")
        return
        
    conn = sqlite3.connect(DB_PATH)
    
    print("--- Daily Metrics ---")
    try:
        df = pd.read_sql("SELECT date, computer_active_seconds, window_events FROM daily_metrics", conn)
        print(df.to_string())
    except Exception as e:
        print(f"Error reading metrics: {e}")
        
    print("\n--- Notes Summary ---")
    try:
        # Group by date
        df_notes = pd.read_sql("SELECT date, COUNT(*) as count FROM notes GROUP BY date", conn)
        if df_notes.empty:
            print("No notes found.")
        else:
            print(df_notes.to_string())
            
        print("\n--- Sample Notes ---")
        df_sample = pd.read_sql("SELECT date, substr(content, 1, 50) as snippet from notes LIMIT 10", conn)
        print(df_sample.to_string())
        
    except Exception as e:
        print(f"Error reading notes: {e}")
        
    conn.close()

if __name__ == "__main__":
    verify()
