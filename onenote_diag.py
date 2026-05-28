import win32com.client

def diagnose_onenote():
    try:
        # Try both generic and version-specific ProgIDs
        print("Attempting to connect to OneNote.Application...")
        onenote = win32com.client.Dispatch("OneNote.Application")
        print("Connected.")
        
        try:
            print("Methods available:", [m for m in dir(onenote) if not m.startswith('_')])
        except:
            print("Could not list methods.")

        # Try GetHierarchy with just 2 args (most common python mapping)
        try:
            # HierarchyScope.hsNotebooks = 0
            xml_out = onenote.GetHierarchy("", 0)
            print("GetHierarchy succeeded.")
            print("First 100 chars of XML:", xml_out[:100] if xml_out else "None")
        except Exception as e:
            print(f"GetHierarchy failed: {e}")

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    diagnose_onenote()
