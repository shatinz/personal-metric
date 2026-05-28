import win32com.client

def test_ensure():
    try:
        # Use EnsureDispatch to force early binding
        print("Using EnsureDispatch...")
        onenote = win32com.client.gencache.EnsureDispatch("OneNote.Application")
        print("Connected with early binding.")
        
        # Try to call GetHierarchy
        # Signature: GetHierarchy(bstrStartNodeID, hsScope, bstrHierarchyXmlOut) in specific versions?
        # Usually returns XML string as return value in Python wrapper.
        
        # Test 1: Standard call
        try:
            xml = onenote.GetHierarchy("", 0) # 0 = hsNotebooks
            if xml:
                print(f"Success! XML length: {len(xml)}")
                print(xml[:200])
        except Exception as e:
            print(f"Standard call failed: {e}")
            
    except Exception as e:
        print(f"EnsureDispatch failed: {e}")
        # Fallback to dynamic dispatch
        try:
            print("Falling back to Dispatch...")
            onenote = win32com.client.Dispatch("OneNote.Application")
            xml = onenote.GetHierarchy("", 0)
            print(f"Success! XML length: {len(xml)}")
        except Exception as e2:
            print(f"Dynamic failed too: {e2}")

if __name__ == "__main__":
    test_ensure()
