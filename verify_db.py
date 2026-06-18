import sqlite3

def check_db():
    conn = sqlite3.connect("personal_metric.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT count(*) FROM notes")
    count = cursor.fetchone()[0]
    print(f"Total notes in database: {count}")
    
    cursor.execute("SELECT date FROM notes ORDER BY date LIMIT 1")
    first = cursor.fetchone()
    print(f"First note date: {first[0] if first else 'N/A'}")

    cursor.execute("SELECT date FROM notes ORDER BY date DESC LIMIT 1")
    last = cursor.fetchone()
    print(f"Last note date: {last[0] if last else 'N/A'}")
    
    # Check for the specific date the user wanted before
    cursor.execute("SELECT date FROM notes WHERE date = '2026-02-01'")
    feb1 = cursor.fetchone()
    print(f"Found Feb 1st note: {'Yes' if feb1 else 'No'}")
    
    conn.close()

if __name__ == '__main__':
    check_db()
