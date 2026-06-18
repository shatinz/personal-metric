import win32com.client
import xml.etree.ElementTree as ET
import re

def test_extract():
    try:
        onenote = win32com.client.Dispatch("OneNote.Application")
        # Get hierarchy of pages (hsPages = 4)
        xml_str = onenote.GetHierarchy("", 4)
        tree = ET.fromstring(xml_str)
        ns = '{http://schemas.microsoft.com/office/onenote/2013/onenote}'
        
        pages = tree.findall(f".//{ns}Page")
        print(f"Found {len(pages)} pages.")
        
        if not pages:
            return
            
        # Get the first page's content
        page_id = pages[0].get('ID')
        page_date = pages[0].get('dateTime')
        print(f"Page Date: {page_date}")
        
        page_xml = onenote.GetPageContent(page_id)
        page_tree = ET.fromstring(page_xml)
        
        # Extract text from the page XML
        texts = []
        for t in page_tree.findall(f".//{ns}T"):
            # The text inside <one:T> tag might contain CDATA or plain text
            if t.text:
                # remove html tags if any using regex
                clean_text = re.sub(r'<[^>]+>', '', t.text)
                texts.append(clean_text)
                
        print("Sample Text Content:")
        for t in texts[:5]:
             print(f"- {t.strip()}")
             
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_extract()
