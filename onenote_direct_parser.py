from pyOneNote.OneDocument import OneDocment
import sys
import os

FILE_PATH = r"C:\Users\PC\Documents\OneNote Notebooks\Personal notes\dailynotes.one"

def decode_hex_if_possible(s):
    # Check if string is valid hex and even length
    if len(s) % 2 != 0:
        return None
    # Check chars
    if not all(c in '0123456789abcdefABCDEF' for c in s):
        return None
    try:
        b = bytes.fromhex(s)
        # Try decoding as utf-8 or latin-1
        # Removing null bytes which are common in wide strings
        decoded = b.decode('utf-8').replace('\x00', '')
        # Basic heuristic: mostly printable?
        if len(decoded) > 5 and sum(c.isalnum() or c.isspace() for c in decoded) / len(decoded) > 0.7:
             return decoded
    except:
        pass
    return None

def extract_strings_from_json(data, texts):
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str) and len(v) > 10:
                # Try to decode
                decoded = decode_hex_if_possible(v)
                if decoded:
                    texts.append(decoded)
                # else: texts.append(v) # Optional: keep original if not hex
            else:
                 extract_strings_from_json(v, texts)
    elif isinstance(data, list):
        for item in data:
            extract_strings_from_json(item, texts)

def main():
    if not os.path.exists(FILE_PATH):
        print("File not found.")
        return

    print(f"Reading {FILE_PATH}...")
    try:
        with open(FILE_PATH, "rb") as f:
            doc = OneDocment(f)
            data = doc.get_json() # Returns a huge dict
            
        print(f"JSON Keys: {list(data.keys())}")
        
        all_text = []
        extract_strings_from_json(data, all_text)
        
        unique_texts = sorted(list(set(all_text)), key=len, reverse=True)
        print(f"Found {len(unique_texts)} strings.")
        
        print("--- Sample Content ---")
        for t in unique_texts[:20]:
            # Filter likely binary/hex garbage if any
            if any(c for c in t if ord(c) < 32 and c not in '\n\r\t'):
                continue
            print(f"- {t.strip()}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
