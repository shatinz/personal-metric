import win32com.client
import sys
import platform

def test_active_object():
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.architecture()}")
    
    try:
        # Connect to running instance
        print("Connecting to active OneNote instance...")
        onenote = win32com.client.GetActiveObject("OneNote.Application")
        print("Connected.")
        
        # List methods
        try:
            print("Methods:", [m for m in dir(onenote) if not m.startswith('_')])
        except:
            print("Could not list methods via dir()")

        # Try GetHierarchy
        try:
            xml = onenote.GetHierarchy("", 4) # 4 = hsPages
            # If successful, print first 100 chars
            print(f"XML (len={len(xml)}): {xml[:100]}")
        except Exception as e:
            print(f"GetHierarchy error: {e}")
            
    except Exception as e:
        print(f"Failed to get active object: {e}")
        # Try Dispatch fallback
        try:
            print("Falling back to Dispatch...")
            onenote = win32com.client.Dispatch("OneNote.Application")
            xml = onenote.GetHierarchy("", 4)
            print(f"XML (len={len(xml)}): {xml[:100]}")
        except Exception as e2:
            print(f"Dispatch fallback error: {e2}")

if __name__ == "__main__":
    test_active_object()
