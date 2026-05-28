import win32com.client
import xml.etree.ElementTree as ET

def connect_onenote():
    try:
        onenote = win32com.client.Dispatch("OneNote.Application")
        return onenote
    except Exception as e:
        print(f"Error connecting to OneNote: {e}")
        return None

def get_notebooks(onenote):
    xml_str = onenote.GetHierarchy("", win32com.client.constants.hsNotebooks)
    tree = ET.fromstring(xml_str)
    
    notebooks = []
    # Identify namespace if present (OneNote XML usually has one)
    ns = {'one': 'http://schemas.microsoft.com/office/onenote/2013/onenote'}
    
    for notebook in tree.findall(".//{http://schemas.microsoft.com/office/onenote/2013/onenote}Notebook"):
        name = notebook.get('name')
        notebook_id = notebook.get('ID')
        notebooks.append((name, notebook_id))
        print(f"Found notebook: {name}")
        
    return notebooks

def find_target_section(onenote, notebook_name="personalnotes", section_name="dailynotes"):
    xml_str = onenote.GetHierarchy("", win32com.client.constants.hsSections)
    # Using lxml or simplified parsing if namespace is tricky
    # Let's try parsing with namespace awareness
    # Note: Onenote XML Namespace is tricky. Let's do simple string search or robust XML parsing.
    
    # Simple approach: Get XML of ALL hierarchies and search
    # Better: Get list of notebooks -> expand target notebook -> find section
    
    # 1. Get Notebook ID
    notebooks = get_notebooks(onenote)
    target_nb_id = None
    for name, nid in notebooks:
        if name.lower() == notebook_name.lower():
            target_nb_id = nid
            break
            
    if not target_nb_id:
        print(f"Notebook '{notebook_name}' not found.")
        return None

    # 2. Get Sections in Notebook
    xml_sections = onenote.GetHierarchy(target_nb_id, win32com.client.constants.hsSections)
    tree = ET.fromstring(xml_sections)
    
    # Find section
    target_section_id = None
    for section in tree.findall(".//{http://schemas.microsoft.com/office/onenote/2013/onenote}Section"):
        s_name = section.get('name')
        if s_name.lower() == section_name.lower():
            target_section_id = section.get('ID')
            print(f"Found section: {s_name} (ID: {target_section_id})")
            break
            
    if not target_section_id:
        print(f"Section '{section_name}' not found in notebook '{notebook_name}'.")
        
    return target_section_id

if __name__ == "__main__":
    app = connect_onenote()
    if app:
        print("Connected to OneNote Application.")
        get_notebooks(app)
        
        # Try to find the specific section
        sec_id = find_target_section(app, "personalnotes", "dailynotes")
        if sec_id:
            print(f"SUCCESS: Found target section ID: {sec_id}")
        else:
            print("WARNING: Could not find target section.")
