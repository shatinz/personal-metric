import win32com.client
import xml.etree.ElementTree as ET
import re
import datetime

def get_all_notes(file_path_ignored=None):
    """
    Connects to local OneNote via COM and extracts notes from Personal notes -> dailynotes.
    Returns a list of dicts: [{'content': str, 'date': str}]
    """
    try:
        try:
            onenote = win32com.client.GetActiveObject("OneNote.Application")
            print("Connected to active OneNote application.")
        except Exception:
            print("OneNote is not currently running in the same user session. Trying to launch it...")
            try:
                onenote = win32com.client.gencache.EnsureDispatch("OneNote.Application")
            except Exception:
                # Fallback to dynamic dispatch
                onenote = win32com.client.Dispatch("OneNote.Application")
            print("Connected to OneNote application.")
        
        # 1. Get Notebooks
        xml_str = onenote.GetHierarchy("", 0) # 0 = hsNotebooks
        tree = ET.fromstring(xml_str)
        ns = {'one': 'http://schemas.microsoft.com/office/onenote/2013/onenote'}
        
        target_nb_id = None
        for nb in tree.findall(".//one:Notebook", ns):
            if nb.get('name', '').lower().replace(' ', '') == "personalnotes":
                target_nb_id = nb.get('ID')
                break
                
        if not target_nb_id:
            print("Could not find 'Personal notes' notebook.")
            return []
            
        # 2. Get Sections
        xml_sections = onenote.GetHierarchy(target_nb_id, 2) # 2 = hsSections
        tree = ET.fromstring(xml_sections)
        target_sec_id = None
        for sec in tree.findall(".//one:Section", ns):
            if sec.get('name', '').lower() == "dailynotes":
                target_sec_id = sec.get('ID')
                break
                
        if not target_sec_id:
            print("Could not find 'dailynotes' section.")
            return []
            
        # 3. Get Pages
        xml_pages = onenote.GetHierarchy(target_sec_id, 4) # 4 = hsPages
        tree = ET.fromstring(xml_pages)
        
        results = []
        for page in tree.findall(".//one:Page", ns):
            page_id = page.get('ID')
            # Extract date from something like "2026-02-01T10:17:55.000Z"
            page_datetime = page.get('dateTime', '')
            page_date = page_datetime.split('T')[0] if 'T' in page_datetime else page_datetime.split(' ')[0]
            
            try:
                page_xml = onenote.GetPageContent(page_id)
                page_tree = ET.fromstring(page_xml)
                
                # Extract text
                for t in page_tree.findall(".//one:T", ns):
                    if t.text:
                        # Remove CDATA wrapper/HTML tags
                        clean_text = re.sub(r'<[^>]+>', '', t.text)
                        clean_text = clean_text.replace('&nbsp;', ' ').strip()
                        # Deduplicate substrings roughly by skipping tiny fragments
                        if len(clean_text) > 5:
                             results.append({'content': clean_text, 'date': page_date})
            except Exception as e:
                print(f"Failed to get content for page ID {page_id}: {e}")
                
        return results

    except AttributeError as e:
        print(f"\n[!] COM Method Error: {e}")
        print("This usually happens if OneNote is not open, or if the COM library isn't registered properly.")
        print("Please ensure OneNote is OPEN on your desktop and running as the same user (not as Administrator) before running this script.")
        return []
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error extracting notes via COM: {e}")
        return []

if __name__ == "__main__":
    notes = get_all_notes()
    print(f"Extracted {len(notes)} notes.")
    if notes:
        print(f"Sample note: {notes[0]}")
