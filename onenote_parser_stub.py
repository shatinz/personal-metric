from pyOneNote.Main import process_onenote_file
import sys
import os

FILE_PATH = r"C:\Users\PC\Documents\OneNote Notebooks\Personal notes\dailynotes.one"

def inspect_nodes(node, depth=0):
    indent = "  " * depth
    # Try to find text properties
    # This is a guess based on typical OneNote structure (Outline -> OutlineElement -> RichText)
    
    # Generic property dump
    if hasattr(node, "data"):
        # print(f"{indent}Data: {node.data[:20]}...")
        pass
        
    if hasattr(node, "properties"):
        for prop, val in node.properties.items():
            # Look for text-like properties
            # Text is often in 'TextRunIndex' or similar referring to global string table?
            pass

def main():
    if not os.path.exists(FILE_PATH):
        print("File not found.")
        return

    print(f"Processing {FILE_PATH}...")
    try:
        # process_onenote_file(file, output_dir, extension)
        # It might return the doc, or just print?
        # Let's try to capture stdout if it just prints?
        # But we want the object.
        
        # Checking implementation of process_onenote_file via introspection
        # It seems it instantiates OneDoc.
        
        # Let's try to instantiate OneDoc directly if we can find it.
        # It was likely not in Main, but Main imported it?
        pass
    except Exception as e:
        print(e)

# Redefining strategy: Use the library's classes if possible.
# From the error 'ImportError: check pyOneNote structure'
# Let's try finding where OneDoc is.
# python -c "import pyOneNote; print(pyOneNote.__file__)" -> find path -> list dir.

if __name__ == "__main__":
    # Just run the CLI command and parse output for now.
    pass
