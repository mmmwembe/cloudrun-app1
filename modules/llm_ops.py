import pandas as pd
from google.cloud import storage
import os
import uuid
from langchain_groq import ChatGroq
from PyPDF2 import PdfReader
import json
import requests
from bs4 import BeautifulSoup
import tempfile
import re
from langchain_community.document_loaders import PyPDFLoader
import fitz  # PyMuPDF
import hashlib
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
# Get the Google service account JSON from environment variable
secret_json = os.getenv('GOOGLE_SECRET_JSON')

BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'

models_array = ["mixtral-8x7b-32768","llama3-70b-8192","llama3-8b-8192","gemma-7b-it","gemma2-9b-it"]

llm = ChatGroq(
    model="mixtral-8x7b-32768",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY,
    verbose=True,
)

# 1. `get_default_citation()`
# 2. `process_pdf_url(pdf_url)`
# 3. `extract_pdf_info(pdf_url)` (called inside `process_pdf_url`)
# 4. `update_parent_files_tracking(public_url)`
# 5. `read_pdf_from_url(public_url)` (called inside `update_parent_files_tracking`)
# 6. `llm_parsed_output_from_text(pdf_text_content)` (called inside `update_parent_files_tracking`)

# Default Citation
def get_default_citation():
    return {
        'name': "Stuart R. Stidolph Diatom Atlas",
        'full_citation': "Stidolph, S.R., Sterrenburg, F.A.S., Smith, K.E.L., Kraberg, A., 2012, Stuart R. Stidolph Diatom Atlas: U.S. Geological Survey Open-File Report 2012-1163, 199 p., available at http://pubs.usgs.gov/of/2012/1163/.",
        'authors': ["S.R. Stidolph", "F.A.S. Sterrenburg", "K.E.L. Smith", "A. Kraberg"],
        'year': "2012",
        'organization': "U.S. Geological Survey",
        'doi': "",
        'url': "http://pubs.usgs.gov/of/2012/1163/"
}
    
def get_storage_client():
    """Get authenticated GCS client"""
    return storage.Client.from_service_account_info(json.loads(secret_json))

def get_file_hash(file_content):
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()

