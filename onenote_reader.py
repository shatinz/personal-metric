from pyOneNote.Main import OneDoc
from pathlib import Path

FILE_PATH = r"C:\Users\PC\Documents\OneNote Notebooks\Personal notes\dailynotes.one"

def read_onenote_file():
    path = Path(FILE_PATH)
    if not path.exists():
        print(f"File not found: {path}")
        return

    try:
        doc = OneDoc(str(path))
        print(f"Successfully opened {path.name}")
        
        # Traverse nodes (based on pyOneNote examples)
        # pyOneNote is low-level. We probably need to iterate recursively.
        # But let's check what nodes are available.
        # usually parsing strings is handled differently.
        
        # Basic traversal to find text blobs?
        # Note: pyOneNote might not have high-level "get_text()" methods.
        # Let's inspect the keys available in the root file node.
        
        # Simpler approach: Iterate and print types
        # doc.root is the starting point? Or doc.file_nodes?
        
        print("Nodes found:", len(doc.nodes))
        
        # Try to find text content strings
        # This is experimental as pyOneNote is a parser, not a full DOM wrapper.
        # Let's just print finding status
        
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    read_onenote_file()
