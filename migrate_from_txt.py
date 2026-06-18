import sqlite3
import hashlib
import embeddings
import text_normalizer

def main():
    print("Reading and parsing diaryfromonenote.txt using text_normalizer...")
    final_notes = text_normalizer.parse_and_normalize_txt("diaryfromonenote.txt")
    print(f"Found {len(final_notes)} unique, normalized entries.")
    
    print("Connecting to database...")
    conn = sqlite3.connect("personal_metric.db")
    cursor = conn.cursor()
    
    print("WARNING: Clearing all old notes from the database...")
    cursor.execute("DELETE FROM notes")
    conn.commit()
    
    print("Loading embedding model...")
    embedder = embeddings.Embedder()
    
    print("Generating embeddings and inserting into database...")
    new_count = 0
    for note in final_notes:
        note_text = note['content']
        note_date = note['date']
        note_source = note.get('source', 'onenote_txt')
        note_hash = hashlib.md5(note_text.encode('utf-8')).hexdigest()
        
        vec = embedder.embed_text(note_text)
        blob = embedder.serialize_embedding(vec)
        
        cursor.execute(
            "INSERT INTO notes (id, date, content, embedding, source) VALUES (?, ?, ?, ?, ?)",
            (note_hash, note_date, note_text, blob, note_source)
        )
        new_count += 1
        
    conn.commit()
    conn.close()
    print(f"SUCCESS: {new_count} unique notes have been saved to the database.")

if __name__ == '__main__':
    main()
