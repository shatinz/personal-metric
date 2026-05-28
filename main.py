import db
import aw_client_wrapper
import embeddings
import onenote_local  # This needs to be robust
import sqlite3
import datetime
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_today_metrics():
    end_dt = datetime.datetime.now(datetime.timezone.utc)
    start_dt = end_dt - datetime.timedelta(days=1)
    # Actually, we want metrics for a specific DATE (local midnight to midnight).
    # But for now, let's just get last 24h as a proxy or today since midnight.
    
    # Proper day boundary logic:
    today = datetime.date.today()
    start_of_day = datetime.datetime.combine(today, datetime.time.min).replace(tzinfo=datetime.timezone.utc) # naive to utc
    # This timezone handling is tricky. ActivityWatch uses UTC.
    # Let's use local midnight converted to UTC.
    from dateutil import tz
    local_tz = tz.tzlocal()
    now_local = datetime.datetime.now(local_tz)
    start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    
    client, afk, win, android = aw_client_wrapper.get_aw_client(None, None) # client init doesn't need dates
    
    # Calculate for today
    laptop_seconds = aw_client_wrapper.calculate_daily_active_time(client, afk, start_of_day_local, now_local)
        
    top_apps = aw_client_wrapper.get_top_apps(client, win, start_of_day_local, now_local, limit=5)
    
    return today, laptop_seconds, top_apps

def update_onenote_embeddings(db_conn, embedder):
    """
    Reads notes from .one file, hashes them, and stores new ones with embeddings.
    """
    import onenote_extractor 
    import config
    import hashlib
    
    notes = onenote_extractor.get_all_notes(config.ONENOTE_PATH)
    logging.info(f"Found {len(notes)} text fragments in OneNote file.")
    
    cursor = db_conn.cursor()
    new_count = 0
    
    # Collect unique dates affected
    affected_dates = set()
    for note in notes:
        # Parse date from "2026-02-08 10:17:55"
        try:
             note_date = note['date'].split(" ")[0]
        except:
             note_date = datetime.date.today().isoformat()
        affected_dates.add(note_date)
        
    logging.info(f"Syncing notes for dates: {sorted(list(affected_dates))}")
    
    # Prune existing notes for these dates (Full Sync Strategy)
    for d in affected_dates:
        cursor.execute("DELETE FROM notes WHERE date = ?", (d,))
    
    for note in notes:
        note_text = note['content']
        try:
             note_date = note['date'].split(" ")[0]
        except:
             # Should match above
             note_date = datetime.date.today().isoformat()
        
        # Generate ID based on content hash
        note_hash = hashlib.md5(note_text.encode('utf-8')).hexdigest()
            
        # New note: generate embedding
        if embedder and note_text:
            vec = embedder.embed_text(note_text)
            blob = embedder.serialize_embedding(vec)
            
            cursor.execute("INSERT INTO notes (id, date, content, embedding) VALUES (?, ?, ?, ?)",
                           (note_hash, note_date, note_text, blob))
            new_count += 1
            
    db_conn.commit()
    return new_count

def main():
    # 1. Init DB
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    
    # 2. Daily Metrics
    try:
        today, laptop_sec, top_apps = get_today_metrics()
        logging.info(f"Metrics for {today}: PC={laptop_sec/3600:.1f}h")
        
        # Upsert into DB
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO daily_metrics (date, computer_active_seconds, window_events)
            VALUES (?, ?, ?)
        ''', (today, laptop_sec, json.dumps(top_apps)))
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating daily metrics: {e}")

    # 3. Embeddings
    try:
        embedder = embeddings.Embedder() # Load model
        count = update_onenote_embeddings(conn, embedder)
        logging.info(f"Processed {count} new notes.")
    except Exception as e:
        logging.error(f"Error in embedding process: {e}")
        
    conn.close()
    logging.info("Sync complete.")

if __name__ == "__main__":
    main()
