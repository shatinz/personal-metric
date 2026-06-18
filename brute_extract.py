import re

FILE_PATH = r"C:\Users\PC\Documents\OneNote Notebooks\Personal notes\dailynotes.one"

def extract_strings():
    with open(FILE_PATH, 'rb') as f:
        content = f.read()
    
    # Extract wide strings (UTF-16LE)
    # Looking for sequences of printable ascii separated by null bytes
    wide_pattern = re.compile(b'(?:[\x20-\x7E]\x00){5,}')
    
    strings = []
    for match in wide_pattern.finditer(content):
        try:
            s = match.group(0).decode('utf-16le')
            strings.append(s)
        except:
            pass
            
    # Also extract UTF-8/ASCII strings
    ascii_pattern = re.compile(b'[\x20-\x7E]{5,}')
    for match in ascii_pattern.finditer(content):
        try:
            s = match.group(0).decode('ascii')
            strings.append(s)
        except:
            pass

    found_dates = set()
    found_content = []
    
    for s in strings:
        if '2026-02-01' in s:
            found_dates.add(s)
            
    if found_dates:
        print("Found mentions of 2026-02-01:")
        for d in found_dates:
            print(f"- {d}")
    else:
        print("No mentions of 2026-02-01 found in the raw binary strings.")
        
    # Let's print out all dates that look like 2026-02-XX just to see
    all_dates = set()
    date_regex = re.compile(r'2026-02-\d{2}')
    for s in strings:
        for match in date_regex.findall(s):
            all_dates.add(match)
            
    print(f"All dates found in February 2026: {sorted(list(all_dates))}")
    
    # Try to find a paragraph near "2026-02-01"
    for i, s in enumerate(strings):
        if '2026-02-01' in s:
            print("--- Context around mention ---")
            start = max(0, i-5)
            end = min(len(strings), i+5)
            for j in range(start, end):
                print(f"[{j-i}] {strings[j]}")

if __name__ == "__main__":
    extract_strings()
