import db
import aw_client_wrapper
import embeddings
import onenote_local  # This needs to be robust
import sqlite3
import datetime
import json
import logging
import hashlib
import gdocs_extractor
import nlp_analysis
import dynamic_clustering
import ai_evaluator
from config import DB_PATH, GDOCS_CREDENTIALS_FILE, GDOCS_DOCUMENT_ID

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
    Reads notes from Google Docs, hashes them, and stores new ones with embeddings.
    """
    cursor = db_conn.cursor()
    
    print("Fetching notes from Google Docs...")
    try:
        notes_data = gdocs_extractor.extract_notes(GDOCS_CREDENTIALS_FILE, GDOCS_DOCUMENT_ID)
    except Exception as e:
        print(f"Failed to fetch Google Docs: {e}")
        notes_data = []

    print(f"Found {len(notes_data)} entries in Google Docs.")

    # 4. Save to Database
    new_notes_count = 0
    synced_dates = []
    
    for note in notes_data:
        note_date = note['date']
        note_text = note['content']
        mood = note['mood']
        energy = note['energy']
        focus = note['focus']
        location = note['location']

        # Skip completely empty entries
        if not note_text and mood is None and energy is None and focus is None:
            continue

        # Create deterministic ID based on date and text
        note_hash = hashlib.md5((note_date + note_text).encode('utf-8')).hexdigest()
        
        # Check if already exists
        cursor.execute("SELECT 1 FROM notes WHERE id=?", (note_hash,))
        if cursor.fetchone():
            continue # Skip

        # Generate Embedding (we embed the text and metrics together for better semantic search)
        embedded_string = f"Date: {note_date}. Mood: {mood}. Energy: {energy}. Focus: {focus}. Location: {location}. {note_text}"
        vec = embedder.embed_text(embedded_string)
        blob = embedder.serialize_embedding(vec)
        
        # Insert
        cursor.execute("""
            INSERT INTO notes (id, date, content, embedding, mood, energy, focus, location) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (note_hash, note_date, note_text, blob, mood, energy, focus, location))
        
        new_notes_count += 1
        synced_dates.append(note_date)
        
    db_conn.commit()
    
    logging.info(f"Syncing notes for dates: {synced_dates}")
    logging.info(f"Processed {new_notes_count} new notes.")
    return new_notes_count

def main():
    # 1. Init DB
    db.init_db()
    conn = sqlite3.connect(DB_PATH)
    
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

    # 4. NLP Analysis (runs only on new/unanalyzed notes)
    try:
        logging.info("Running NLP analysis pipeline...")
        analyzed = nlp_analysis.run_analysis_pipeline(str(DB_PATH))
        logging.info(f"NLP analysis complete: {analyzed} entries processed.")
    except Exception as e:
        logging.error(f"Error in NLP analysis: {e}")

    # 5. Dynamic Clustering (full re-cluster on each run)
    try:
        logging.info("Running dynamic clustering pipeline...")
        cluster_result = dynamic_clustering.run_clustering_pipeline(str(DB_PATH))
        if cluster_result.get('status') == 'success':
            logging.info(
                f"Clustering complete: "
                f"HDBSCAN={cluster_result['hdbscan']['n_clusters']} clusters, "
                f"K-Means K={cluster_result['kmeans']['optimal_k']} "
                f"(sil={cluster_result['kmeans']['silhouette_score']:.3f})"
            )
        else:
            logging.warning(f"Clustering skipped: {cluster_result.get('reason', 'unknown')}")
    except Exception as e:
        logging.error(f"Error in clustering pipeline: {e}")

    # 6. AI Evaluation (optional — comment out if not needed on every run)
    try:
        logging.info("Running AI evaluation...")
        report = ai_evaluator.run_ai_evaluation(str(DB_PATH))
        report_path = 'latest_evaluation.md'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logging.info(f"AI evaluation saved to {report_path}")
    except Exception as e:
        logging.error(f"Error in AI evaluation: {e}")

    logging.info("Sync complete.")

if __name__ == "__main__":
    main()
