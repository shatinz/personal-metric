import sqlite3
import pandas as pd
import sys

DATE = "2026-02-06"
if len(sys.argv) > 1:
    DATE = sys.argv[1]

conn = sqlite3.connect('personal_metric.db')
print(f"--- Notes for {DATE} ---")
try:
    df = pd.read_sql(f"SELECT content FROM notes WHERE date='{DATE}'", conn)
    if df.empty:
        print("No notes found.")
    else:
        # Print full content to show user
        for idx, row in df.iterrows():
            print(f"[{idx+1}] {row['content']}")
            print("-" * 40)
except Exception as e:
    print(e)
conn.close()
