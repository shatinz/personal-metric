from pyOneNote.OneDocument import OneDocment
import datetime

FILE_PATH = r"C:\Users\PC\Documents\OneNote Notebooks\Personal notes\dailynotes.one"

def find_identity_dates(data):
    # Map identity -> date
    id_date_map = {}
    
    # Check 'properties' list
    if 'properties' in data and isinstance(data['properties'], list):
        for prop in data['properties']:
            if 'identity' in prop and 'val' in prop:
                # Check for LastModifiedTime in val
                val = prop['val']
                if 'LastModifiedTime' in val:
                    id_date_map[prop['identity']] = val['LastModifiedTime']
    return id_date_map

def main():
    try:
        with open(FILE_PATH, "rb") as f:
            doc = OneDocment(f)
            data = doc.get_json()
            
        print("Building date map...")
        date_map = find_identity_dates(data)
        print(f"Found {len(date_map)} timestamps.")
        
        # Now traverse 'files' and see if we can link text to these IDs
        # The 'files' dict has keys which look like names, and values with 'identity'
        
        if 'files' in data:
            print(f"Scanning {len(data['files'])} files/nodes...")
            for name, file_info in data['files'].items():
                ident = file_info.get('identity')
                date = date_map.get(ident, "Unknown")
                
                content = file_info.get('content', b'')
                # The content here is bytes.
                # In previous steps, I extracted text from the JSON values recursively.
                # If 'content' is bytes, pyOneNote might not have fully parsed the internal text of that node in get_json?
                # accessing 'val' in properties might have the text?
                
                # Let's check where the text came from in my previous success.
                # I was iterating the WHOLE json. 
                # So text might be in 'properties' -> 'val' -> 'TextRunIndex' ??
                pass
                
        # Re-scan whole JSON looking for text and checking if siblings have identity
        # Actually, let's just dump text found near an identity.
        
        def scan_for_text_and_id(node, parent_id=None):
            if isinstance(node, dict):
                current_id = node.get('identity', parent_id)
                
                # Check for text
                for k, v in node.items():
                    if isinstance(v, str) and len(v) > 20 and not k == 'identity':
                        # Check if this value looks like hex text
                        # (Reuse decode logic if we want, but just printing raw is fine for now)
                        if date_map.get(current_id):
                             print(f"Found text with Date {date_map[current_id]}: {v[:30]}...")
                             
                for k, v in node.items():
                    if isinstance(v, (dict, list)):
                        scan_for_text_and_id(v, current_id)
            elif isinstance(node, list):
                for item in node:
                    scan_for_text_and_id(item, parent_id)

        scan_for_text_and_id(data)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
