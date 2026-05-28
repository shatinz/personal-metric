import sqlite3
import json
from datetime import date
from pathlib import Path

DB_PATH = Path("personal_metric.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date DATE PRIMARY KEY,
            computer_active_seconds REAL,
            window_events JSON
        )
    ''')
    
    # notes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            date DATE,
            content TEXT,
            embedding BLOB
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH.absolute()}")

if __name__ == "__main__":
    init_db()
