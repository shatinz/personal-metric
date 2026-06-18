"""
text_normalizer.py
==================
Handles the structural differences between:
  1. Old OneNote .txt format  -> date/time header lines, bare text body
  2. New Google Docs format   -> already structured with mood/energy/focus fields

Returns a normalized dict: { 'date': str, 'content': str, 'source': str }
where 'content' is ONLY the clean narrative text (no metadata).
"""

import re
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# REGEX PATTERNS
# ─────────────────────────────────────────────────────────────────────────────
# Matches: "Sunday, February 1, 2026"
_ONENOTE_DATE_RE = re.compile(
    r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
    r'([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s*$'
)

# Matches: "10:37 AM" or "9:05 PM"
_TIME_LINE_RE = re.compile(r'^\d{1,2}:\d{2}\s+[AP]M$')

# Matches structured Google Docs metadata lines like:
# "Mood: 7", "Energy: 8", "Focus: 6", "Location: Home"
_GDOCS_META_RE = re.compile(
    r'^(Mood|Energy|Focus|Location|Date)\s*:\s*.+$', re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def normalize_onenote_entry(date_str: str, raw_lines: list[str]) -> dict:
    """
    Normalizes a raw OneNote entry (already split by date headers) 
    into clean content.
    """
    clean_lines = []
    for line in raw_lines:
        stripped = line.strip()
        # Skip time lines
        if _TIME_LINE_RE.match(stripped):
            continue
        # Skip Google Doc-style metadata that might have leaked in
        if _GDOCS_META_RE.match(stripped):
            continue
        clean_lines.append(stripped)

    # Remove leading/trailing blank lines
    content = '\n'.join(clean_lines).strip()
    # Collapse multiple blank lines into one
    content = re.sub(r'\n{3,}', '\n\n', content)

    return {
        'date': date_str,
        'content': content,
        'source': 'onenote_txt'
    }


def normalize_gdocs_entry(note: dict) -> dict:
    """
    Normalizes a Google Docs entry (already structured dict from gdocs_extractor)
    into the same clean format. Strips metadata fields from the content.
    """
    raw_content = note.get('content', '')
    
    clean_lines = []
    for line in raw_content.split('\n'):
        stripped = line.strip()
        if _GDOCS_META_RE.match(stripped):
            continue
        clean_lines.append(stripped)
    
    content = '\n'.join(clean_lines).strip()
    content = re.sub(r'\n{3,}', '\n\n', content)

    return {
        'date': note.get('date', ''),
        'content': content,
        'source': 'google_docs',
        # Preserve structured fields
        'mood': note.get('mood'),
        'energy': note.get('energy'),
        'focus': note.get('focus'),
        'location': note.get('location'),
    }


def parse_and_normalize_txt(file_path: str) -> list[dict]:
    """
    Full parser for the old OneNote .txt diary file.
    Handles duplicate entries by deduplicating on (date, content) hash.
    Returns list of normalized entry dicts.
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    entries = []
    current_date = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        match = _ONENOTE_DATE_RE.match(stripped)

        if match:
            # Flush previous entry
            if current_date and current_lines:
                entry = normalize_onenote_entry(current_date, current_lines)
                if entry['content']:
                    entries.append(entry)
            
            # Parse new date
            _, month_str, day_str, year_str = match.groups()
            try:
                dt = datetime.strptime(f"{year_str} {month_str} {day_str}", "%Y %B %d")
                current_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                current_date = None
            current_lines = []
        else:
            if current_date:
                current_lines.append(stripped)

    # Flush final entry
    if current_date and current_lines:
        entry = normalize_onenote_entry(current_date, current_lines)
        if entry['content']:
            entries.append(entry)

    # Deduplicate: keep latest version of any duplicate content
    seen = {}
    for e in entries:
        key = e['content']
        if key not in seen:
            seen[key] = e
    
    result = sorted(seen.values(), key=lambda x: x['date'])
    return result


def normalize_gdocs_entries(notes_data: list[dict]) -> list[dict]:
    """
    Normalizes a list of Google Docs entries from gdocs_extractor.
    """
    result = []
    for note in notes_data:
        normalized = normalize_gdocs_entry(note)
        if normalized['content']:
            result.append(normalized)
    return result


if __name__ == '__main__':
    # Quick test on the local txt file
    entries = parse_and_normalize_txt('diaryfromonenote.txt')
    print(f"Parsed {len(entries)} unique OneNote entries.")
    if entries:
        print(f"\n--- Sample entry ({entries[0]['date']}) ---")
        print(entries[0]['content'][:300])
