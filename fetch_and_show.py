import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from gdocs_extractor import extract_notes
from config import GDOCS_CREDENTIALS_FILE, GDOCS_DOCUMENT_ID

entries = extract_notes(GDOCS_CREDENTIALS_FILE, GDOCS_DOCUMENT_ID)
print(f"Total entries: {len(entries)}")
for e in entries:
    print(f"\n=== DATE: {e['date']} ===")
    print(f"Mood: {e['mood']} | Energy: {e['energy']} | Focus: {e['focus']}")
    print(e['content'])
