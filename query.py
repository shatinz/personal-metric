import sqlite3

conn = sqlite3.connect('personal_metric.db')
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT date FROM notes ORDER BY date DESC")
rows = cursor.fetchall()
if rows:
    print("Dates with notes:")
    for row in rows:
        print(row[0])
else:
    print('No notes found for 2026-02-01')
