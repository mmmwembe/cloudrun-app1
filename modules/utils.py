import os
import tempfile
import requests
from PyPDF2 import PdfReader
import shutil

def extract_text_from_pdf(pdf_url):
   """
   Downloads PDF from URL to temp directory, extracts text, then cleans up.
   
   Args:
       pdf_url (str): The URL of the PDF file
   
   Returns:
       str: Extracted text from the PDF
   """
   try:
       # Create temporary file with proper extension
       temp_dir = tempfile.mkdtemp()
       temp_pdf_path = os.path.join(temp_dir, 'temp.pdf')
       
       # Download the file
       response = requests.get(pdf_url)
       response.raise_for_status()  # Raise exception for bad status codes
       
       # Save to temp file
       with open(temp_pdf_path, 'wb') as f:
           f.write(response.content)
       
       # Extract text
       reader = PdfReader(temp_pdf_path)
       text = ""
       for page in reader.pages:
           text += page.extract_text()
           
       return text
       
   except Exception as e:
       print(f"Error processing PDF: {str(e)}")
       return ""
       
   finally:
       # Clean up temp directory and its contents
       if os.path.exists(temp_dir):
           shutil.rmtree(temp_dir)