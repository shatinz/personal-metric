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
            date TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
            mood INTEGER,
            energy INTEGER,
            focus INTEGER,
            location TEXT,
            source TEXT DEFAULT 'unknown'
        )
    ''')
    
    # NLP analysis results table (separate from notes, fully repeatable)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS note_analysis (
            note_id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            -- Lexical metrics
            word_count INTEGER,
            unique_word_count INTEGER,
            word_diversity REAL,
            avg_sentence_length REAL,
            -- Grammatical structure metrics
            verb_ratio REAL,
            noun_ratio REAL,
            adjective_ratio REAL,
            adverb_ratio REAL,
            first_person_pronoun_ratio REAL,
            grammatical_error_count INTEGER,
            grammatical_correctness_score REAL,
            -- Creativity/style metrics
            hapax_legomena_ratio REAL,
            sentence_length_variance REAL,
            creativity_score REAL,
            -- Emotion metrics
            sentiment_polarity REAL,
            sentiment_subjectivity REAL,
            emotion_joy REAL,
            emotion_sadness REAL,
            emotion_anger REAL,
            emotion_fear REAL,
            emotion_surprise REAL,
            emotion_diversity REAL,
            -- Cluster assignments
            hdbscan_cluster_id INTEGER,
            kmeans_cluster_id INTEGER,
            -- Metadata
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes(id)
        )
    ''')

    # Clustering run results for tracking cluster evolution over time
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clustering_runs (
            run_id TEXT PRIMARY KEY,
            run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            algorithm TEXT NOT NULL,
            n_clusters INTEGER,
            silhouette_score REAL,
            notes_analyzed INTEGER,
            cluster_summary JSON
        )
    ''')

    # Correlation results between clusters and metrics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cluster_correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            cluster_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            correlation_coefficient REAL,
            p_value REAL,
            FOREIGN KEY (run_id) REFERENCES clustering_runs(run_id)
        )
    ''')

    # Try to add new columns if they don't exist (Migration for existing installs)
    migrations = [
        ("notes", "mood INTEGER"),
        ("notes", "energy INTEGER"),
        ("notes", "focus INTEGER"),
        ("notes", "location TEXT"),
        ("notes", "source TEXT DEFAULT 'unknown'"),
    ]
    for table, col_def in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass  # Columns already exist
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH.absolute()}")

if __name__ == "__main__":
    init_db()
