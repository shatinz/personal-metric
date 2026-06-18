import os
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

def get_gdocs_service(credentials_path):
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"Credentials not found at {credentials_path}")
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES)
    service = build('docs', 'v1', credentials=creds)
    return service

def extract_int(val):
    if not val: return None
    match = re.search(r'\d+', val)
    return int(match.group()) if match else None

def parse_gdocs_diary(doc_content):
    full_text = ""
    
    if 'tabs' in doc_content:
        for tab in doc_content.get('tabs', []):
            body = tab.get('documentTab', {}).get('body', {})
            for el in body.get('content', []):
                if 'paragraph' in el:
                    for element in el.get('paragraph').get('elements', []):
                        if 'textRun' in element:
                            full_text += element.get('textRun').get('content')
            full_text += "\n\n"
    elif 'body' in doc_content:
        for el in doc_content.get('body').get('content', []):
            if 'paragraph' in el:
                for element in el.get('paragraph').get('elements', []):
                    if 'textRun' in element:
                        full_text += element.get('textRun').get('content')
                    
    date_regex = re.compile(r'^(?:Date:\s*)?(\d{4}[-/]\d{2}[-/]\d{2})$', re.IGNORECASE)
    
    lines = full_text.split('\n')
    entries = []
    current_entry = None
    
    for line in lines:
        line_clean = line.strip()
        
        match = date_regex.match(line_clean)
        if match:
            parsed_date = match.group(1).replace('/', '-')
            
            # Same date might appear multiple times as header/body mixup, 
            # only start new entry if content was populated, or just overwrite
            if current_entry and current_entry['content']:
                entries.append(current_entry)
            
            # If we just saw this exact date line back-to-back, ignore it.
            if current_entry and current_entry['date'] == parsed_date and not current_entry['content']:
                continue

            current_entry = {
                'date': parsed_date,
                'mood': None,
                'energy': None,
                'focus': None,
                'location': None,
                'content': []
            }
            continue
            
        if current_entry:
            if line_clean.startswith('* Mood:') or line_clean.startswith('Mood:'):
                current_entry['mood'] = extract_int(line_clean.split(':', 1)[1].strip())
            elif line_clean.startswith('* Energy:') or line_clean.startswith('Energy:'):
                current_entry['energy'] = extract_int(line_clean.split(':', 1)[1].strip())
            elif line_clean.startswith('* Focus:') or line_clean.startswith('Focus:'):
                current_entry['focus'] = extract_int(line_clean.split(':', 1)[1].strip())
            elif line_clean.startswith('* Location:') or line_clean.startswith('Location:'):
                current_entry['location'] = line_clean.split(':', 1)[1].strip()
            elif line_clean == 'Quick Metrics' or line_clean == 'Daily Narrative':
                continue # Skip structural headers
            else:
                if line_clean or current_entry['content']:
                    current_entry['content'].append(line_clean)
                    
    if current_entry and current_entry.get('date'):
        entries.append(current_entry)
        
    for entry in entries:
        entry['content'] = '\n'.join(entry['content']).strip()
        
    return entries

def extract_notes(credentials_path, document_id):
    service = get_gdocs_service(credentials_path)
    doc = service.documents().get(documentId=document_id, includeTabsContent=True).execute()
    entries = parse_gdocs_diary(doc)
    return entries

if __name__ == '__main__':
    from config import GDOCS_CREDENTIALS_FILE, GDOCS_DOCUMENT_ID
    print("Fetching Google Doc...")
    entries = extract_notes(GDOCS_CREDENTIALS_FILE, GDOCS_DOCUMENT_ID)
    print(f"Parsed {len(entries)} entries.")
    for e in entries:
        print(f"--- {e['date']} ---")
        print(f"Mood: {e['mood']}, Energy: {e['energy']}, Focus: {e['focus']}, Location: {e['location']}")
        print(e['content'][:100].encode('ascii', 'replace').decode('ascii') + "...")
