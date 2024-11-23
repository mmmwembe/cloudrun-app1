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
