import onenote_extractor
import config

notes = onenote_extractor.get_all_notes(config.ONENOTE_PATH)
found = False
for note in notes:
    if "2026-02-01" in note.get('date', ''):
        print("Found note for 2026-02-01:")
        print(note['content'])
        print('-'*20)
        found = True

if not found:
    print("No notes found for 2026-02-01 in OneNote file.")
    
# Let's also print all available dates to be sure
dates = set([n.get('date', '').split(' ')[0] for n in notes])
print("Available dates in OneNote file:", sorted(list(dates)))
