from pyOneNote.OneDocument import OneDocment
import os
import hashlib
import re

PAGE_DATE_FIELDS = (
    "PageDate",
    "Date",
    "DateTime",
    "CreationTime",
    "CreatedTime",
)

FALLBACK_DATE_FIELDS = (
    "LastModifiedTime",
)

def decode_hex_if_possible(s):
    if len(s) % 2 != 0:
        return None
    if not all(c in '0123456789abcdefABCDEF' for c in s):
        return None
    try:
        b = bytes.fromhex(s)
        decoded = b.decode('utf-8').replace('\x00', '')
        # Filter for readable text
        if len(decoded) > 10 and sum(c.isalnum() or c.isspace() for c in decoded) / len(decoded) > 0.6:
             return decoded
    except:
        pass
    return None

def extract_date_from_value(value, preferred_fields):
    if isinstance(value, dict):
        for field in preferred_fields:
            field_value = value.get(field)
            if isinstance(field_value, str) and field_value.strip():
                return field_value.strip()
    return None

def build_identity_date_maps(data):
    preferred_dates = {}
    fallback_dates = {}

    if 'properties' in data and isinstance(data['properties'], list):
        for prop in data['properties']:
            identity = prop.get('identity')
            val = prop.get('val')
            if not identity or not isinstance(val, dict):
                continue

            preferred_date = extract_date_from_value(val, PAGE_DATE_FIELDS)
            if preferred_date:
                preferred_dates[identity] = preferred_date
                continue

            fallback_date = extract_date_from_value(val, FALLBACK_DATE_FIELDS)
            if fallback_date:
                fallback_dates[identity] = fallback_date

    return preferred_dates, fallback_dates

def extract_content_with_dates(data, preferred_date_map, fallback_date_map, results, current_id=None, current_date=None):
    if isinstance(data, dict):
        # Update context if this node has an identity
        node_id = data.get('identity', current_id)
        node_date = current_date

        if node_id:
            node_date = preferred_date_map.get(node_id, node_date)
            if node_date is None:
                node_date = fallback_date_map.get(node_id)

        properties = data.get('properties')
        if isinstance(properties, list):
            for prop in properties:
                val = prop.get('val')
                preferred_date = extract_date_from_value(val, PAGE_DATE_FIELDS)
                if preferred_date:
                    node_date = preferred_date
                    break
            if node_date is None:
                for prop in properties:
                    val = prop.get('val')
                    fallback_date = extract_date_from_value(val, FALLBACK_DATE_FIELDS)
                    if fallback_date:
                        node_date = fallback_date
                        break
        
        for k, v in data.items():
            if isinstance(v, str) and len(v) > 10 and k != 'identity':
                # Decode or use raw
                text = decode_hex_if_possible(v)
                if not text:
                    # Check if it's already readable text
                    # (Simple heuristic: looks like sentence?)
                    if " " in v and sum(c.isalnum() for c in v) > len(v)*0.5:
                        text = v
                
                if text:
                    if node_date:
                        # Parse date string to object or keep string?
                        # OneNote date format: "2026-02-08 10:17:55"
                        results.append({'content': text, 'date': node_date})
            
            elif isinstance(v, (dict, list)):
                extract_content_with_dates(v, preferred_date_map, fallback_date_map, results, node_id, node_date)
                
    elif isinstance(data, list):
        for item in data:
            extract_content_with_dates(item, preferred_date_map, fallback_date_map, results, current_id, current_date)

def get_all_notes(file_path):
    """
    Returns a list of dicts: {'content': str, 'date': str}
    """
    if not os.path.exists(file_path):
        print(f"OneNote file not found: {file_path}")
        return []

    try:
        with open(file_path, "rb") as f:
            doc = OneDocment(f)
            data = doc.get_json()
            
        preferred_date_map, fallback_date_map = build_identity_date_maps(data)
        results = []
        extract_content_with_dates(data, preferred_date_map, fallback_date_map, results)
        
        # Filter out timestamp strings
        # Matches YYYY-MM-DD HH:MM:SS or similar
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}$')
        
        cleaned_results = []
        for r in results:
            content = r['content'].strip()
            # Skip if it looks like a date
            if date_pattern.match(content):
                continue
            cleaned_results.append({'content': content, 'date': r['date']})
            
        # Deduplicate substrings (keep longest)
        # Sort by length descending
        cleaned_results.sort(key=lambda x: len(x['content']), reverse=True)
        
        final_notes = []
        seen_content = []
        
        for r in cleaned_results:
            txt = r['content']
            # Check if this text is a substring of any already accepted text (for the same date?)
            # Safer to just dedupe exact matches first, substring might be dangerous if they are distinct thoughts ("I ran." vs "I ran fast.").
            # But user said "edited ones".
            # Let's simple check: if 'txt' is in 'seen_content', skip.
            # But what if 'txt' is "Hello" and seen is "Hello World"?
            # If user replaced "Hello" with "Hello World", we want "Hello World".
            # Since we sorted by length desc, "Hello World" comes first.
            # So if "Hello" is a substring of "Hello World", we skip "Hello".
            
            is_substring = False
            for seen in seen_content:
                if txt in seen:
                    is_substring = True
                    break
            
            if not is_substring:
                final_notes.append(r)
                seen_content.append(txt)
            
        return final_notes
        
    except Exception as e:
        print(f"Error extracting notes: {e}")
        return []
