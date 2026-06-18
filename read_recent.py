import sqlite3
conn = sqlite3.connect('personal_metric.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", c.fetchall())

# Try to get recent entries
c.execute("SELECT date, content FROM notes ORDER BY date DESC LIMIT 10")
rows = c.fetchall()
for r in rows:
    print("\n===DATE:", r[0])
    print(r[1][:2000])
conn.close()
