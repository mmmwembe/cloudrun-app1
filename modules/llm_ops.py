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
# GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
# Get the Google service account JSON from environment variable
secret_json = os.getenv('GOOGLE_SECRET_JSON')

BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'

#models_array = ["mixtral-8x7b-32768","llama3-70b-8192","llama3-8b-8192","gemma-7b-it","gemma2-9b-it"]
models_array = models = ["gemma-7b-it", "gemma2-9b-it", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "llama-3.2-11b-text-preview", "llama-3.2-11b-vision-preview", "llama-3.2-1b-preview", "llama-3.2-3b-preview", "llama-3.2-90b-text-preview", "llama-3.2-90b-vision-preview", "llama-guard-3-8b", "llama3-70b-8192", "llama3-8b-8192", "llama3-groq-70b-8192-tool-use-preview", "llama3-groq-8b-8192-tool-use-preview", "llava-v1.5-7b-4096-preview", "mixtral-8x7b-32768"]

llm = ChatGroq(
    model="llava-v1.5-7b-4096-preview", #"mixtral-8x7b-32768",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=GROQ_API_KEY,
    verbose=True,
)

def parse_output(ai_msg):
    ai_msg_content = ai_msg.content.strip("```").strip()

    # Remove any non-JSON prefix
    start_idx = ai_msg_content.find("{")
    if start_idx != -1:
        ai_msg_content = ai_msg_content[start_idx:]

    try:
        output_dict = json.loads(ai_msg_content)
        return output_dict
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {str(e)}")
        print("Content:")
        print(ai_msg_content)
        return None

def create_messages(diatom_text):
    """
    Creates messages for the language model.

    Args:
        diatom_text (str): Text containing diatom species information.

    Returns:
        list: Messages for the language model.
    """
    messages = [
        (
            "system",
            """
              You are a helpful diatomist assistant that extracts information from text and provides it in JSON format.

              There should be no preamble or introductory or concluding remarks.

              If information is missing or unclear, leave the corresponding field empty.

              The output should be a markdown code snippet formatted in the following schema, including the leading and trailing "\`\`\`json" and "\`\`\`":

              {
                  "figure_caption": "Plate 3: Marine Diatoms from the Azores",
                  "source_material_location": "South East coast of Faial, Caldeira Inferno",
                  "source_material_coordinates": "38° 31' N; 28° 38' W",
                  "source_material_description": "An open crater of a small volcano, shallow and sandy. Gathered from Pinna (molluscs) and stones.",
                  "source_material_date_collected": "June 1st, 1981",
                  "source_material_received_from": "Hans van den Heuvel, Leiden",
                  "source_material_date_received": "March 17th, 1988",
                  "source_material_note": "Material also deposited in Rijksherbarium Leiden, the Netherlands. Aliquot sample and slide also in collection Sterrenburg, Nr. 249.",
                  "diatom_species_array": [
                      {
                          "species_index": 65,
                          "species_name": "Diploneis bombus",
                          "species_authors": ["Cleve-Euler", "Backman"],
                          "species_year": 1922,
                          "species_references": [
                              {
                                  "author": "Hendey",
                                  "year": 1964,
                                  "figure": "pl. 32, fig. 2"
                              },
                              Repeat as necessary
                          ],
                          "formatted_species_name": "Diploneis_bombus",
                          "genus": "Diploneis",
                          "species_magnification": "1000",
                          "species_scale_bar_microns": "30",
                          "species_note": ""
                      },
                      Repeat as necessary
                  ]
              }

              Remember: Do not return any preamble or explanations, return only a pure JSON string surrounded by triple backticks(```)

""",
        ),
        ("human", diatom_text),
    ]
    return messages


def create_diatom_species_df(parsed_output):
    """
    Creates a DataFrame from parsed diatom species information.

    Args:
        parsed_output (dict): Parsed output from language model.

    Returns:
        pandas.DataFrame or None: DataFrame containing diatom species information, or None if parsing failed.
    """
    if parsed_output:
        diatom_species_df = pd.DataFrame([
            {
                "Index": species["species_index"],
                "Formatted Species Name": species["formatted_species_name"],
                "Species Name": species["species_name"]
            }
            for species in parsed_output["diatom_species_array"]
        ])
        return diatom_species_df
    else:
        print("Failed to parse output.")
        return None


def llm_parsed_output_from_text(pdf_text):
   """
   Process PDF text and return parsed output containing diatom information.

   Args:
       pdf_text (str): Text extracted from PDF

   Returns:
       dict: Parsed output containing diatom information or None if parsing failed
   """
   try:
       # Create messages for LLM
       messages = create_messages(pdf_text)

       # Get response from LLM
       ai_msg = llm.invoke(messages)

       # Parse the output
       parsed_output = parse_output(ai_msg)

       return parsed_output

   except Exception as e:
       print(f"Error processing text: {str(e)}")
       return None


def llm_with_JSON_output(pdf_text):
   """
   Process PDF text and return parsed output containing diatom information.

   Args:
       pdf_text (str): Text extracted from PDF

   Returns:
       dict: Parsed output containing diatom information or None if parsing failed
   """
   try:
       # Create messages for LLM
       messages = create_messages(pdf_text)

       # Get response from LLM
       ai_msg = llm.invoke(messages)

       # Parse the output
       parsed_output = parse_output(ai_msg)

       return parsed_output

   except Exception as e:
       print(f"Error processing text: {str(e)}")
       return None

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
    
def get_default_citation():
    return {
        # Core citation elements
        'authors': ["S.R. Stidolph", "F.A.S. Sterrenburg", "K.E.L. Smith", "A. Kraberg"],  # List of authors in citation format
        'year': "2012",                # Publication year as string
        'title': "Stuart R. Stidolph Diatom Atlas",  # Full title of the work
        'type': "report",              # "article", "report", "book", "chapter", etc.
        
        # Journal-specific fields (empty for non-articles)
        'journal': "",                 # Full journal name
        'volume': "",                  # Volume number as string
        'issue': "",                   # Issue number as string  
        'pages': "199",                # Page range or total pages as string
        
        # Organization-specific fields (empty for articles)
        'organization': "U.S. Geological Survey",  # Publishing institution/organization
        'report_number': "Open-File Report 2012-1163",  # Report ID/number
        
        # Digital identification
        'doi': "",                     # Digital Object Identifier if available
        'url': "http://pubs.usgs.gov/of/2012/1163/",  # Direct URL to publication
        
        # Complete formatted reference
        'full_citation': "Stidolph, S.R., Sterrenburg, F.A.S., Smith, K.E.L., Kraberg, A., 2012, Stuart R. Stidolph Diatom Atlas: U.S. Geological Survey Open-File Report 2012-1163, 199 p., available at http://pubs.usgs.gov/of/2012/1163/"  # Required complete formatted citation
}
    
def get_storage_client():
    """Get authenticated GCS client"""
    return storage.Client.from_service_account_info(json.loads(secret_json))

def get_file_hash(file_content):
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()



def upload_to_gcs(image_content, filename, file_hash, bucket_name):
    """Upload image to Google Cloud Storage and return public URL"""
    try:
        client = get_storage_client()
        #bucket = client.bucket(BUCKET_EXTRACTED_IMAGES)
        bucket = client.bucket(bucket_name)

        # Create blob path using session ID and file hash
        blob_path = f"{SESSION_ID}/{file_hash}/{filename}"
        blob = bucket.blob(blob_path)

        # Upload image
        blob.upload_from_string(image_content, content_type='image/jpeg')

        # Generate public URL
        public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
        return public_url

    except Exception as e:
        print(f"Error uploading to GCS: {str(e)}")
        return None

def save_file_to_bucket(artifact_url, session_id, bucket_name, subdir="papers", subsubdirs=["pdf","word","images","csv","text"]):
    # Determine the subsubdir based on the file extension
    if artifact_url.endswith(".docx"):
        subsubdir = "word"
    elif artifact_url.endswith((".jpg", ".jpeg", ".png", ".gif")):
        subsubdir = "images"
    elif artifact_url.endswith(".csv"):
        subsubdir = "csv"
    elif artifact_url.endswith((".txt", ".text")):
        subsubdir = "text"
    else:
        subsubdir = "pdf"  # Default to PDF if no other match

    client = storage.Client.from_service_account_info(json.loads(secret_json))

    if subsubdir == "word":
        # Delete the contents of the subsubdir before uploading the new file
        blob_prefix = f"{session_id}/{subdir}/{subsubdir}/"
        bucket = client.bucket(bucket_name)
        blobs = client.list_blobs(bucket, prefix=blob_prefix)
        for blob in blobs:
            blob.delete()

    try:
        # Upload the file to Google Cloud Storage
        blob_name = f"{session_id}/{subdir}/{subsubdir}/{os.path.basename(artifact_url)}"
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(artifact_url)
        #print(f"File uploaded to: gs://{bucket_name}/{blob_name}")
        url = blob.public_url
        #print(f"Public URL: {url}")
        return url
    except Exception as e:
        print("An error occurred:", e)
        return None

def extract_pdf_info(pdf_url):
    try:
        # Convert GCS URL to direct download URL
        pdf_url = pdf_url.replace("storage.cloud.google.com", "storage.googleapis.com")

        # Create temporary directory for extracted images
        tmp_dir = "tmp_extracted_images"
        os.makedirs(tmp_dir, exist_ok=True)

        # Download PDF content
        response = requests.get(pdf_url)
        response.raise_for_status()
        pdf_content = response.content

        # Calculate file hash
        file_256_hash = get_file_hash(pdf_content)

        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name

        # Open PDF with PyMuPDF
        pdf_document = fitz.open(temp_path)
        total_pages = len(pdf_document)

        # Initialize result structure
        result = {
            "file_256_hash": file_256_hash,
            "images_in_doc": [],
            "paper_image_urls": []  # New array to store all image URLs
        }

        # Process each page
        for page_num in range(total_pages):
            page = pdf_document[page_num]
            image_list = page.get_images()

            page_info = {
                "page_index": page_num,
                "total_pages": total_pages,
                "has_images": len(image_list) > 0,
                "num_images": len(image_list),
                "image_urls": []
            }

            # Extract images if they exist
            if image_list:
                for img_idx, img in enumerate(image_list, 1):
                    try:
                        # Get image data
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]

                        # Create filename
                        #filename, ext = os.path.splitext(os.path.basename(pdf_url))
                        #image_filename = f"{filename}_page_{page_num + 1}_img_{img_idx}.jpeg"
                        image_filename = f"extracted_img_{page_num + 1}_of_{img_idx}.jpeg"
                        local_path = os.path.join(tmp_dir, image_filename)

                        # Save locally
                        with open(local_path, "wb") as image_file:
                            image_file.write(image_bytes)

                        # Upload to GCS and get URL
                        image_url = upload_to_gcs(
                            image_content=image_bytes,
                            filename=image_filename,
                            file_hash=file_256_hash,
                            bucket_name=BUCKET_EXTRACTED_IMAGES
                        )

                        if image_url:
                            page_info["image_urls"].append(image_url)
                            result["paper_image_urls"].append(image_url)  # Add to consolidated list

                    except Exception as e:
                        print(f"Error processing image {img_idx} on page {page_num + 1}: {str(e)}")

            result["images_in_doc"].append(page_info)

        # Cleanup
        pdf_document.close()
        os.unlink(temp_path)

        # Clean up temporary directory
        for file in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, file))
        os.rmdir(tmp_dir)

        return result

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return None

def process_pdf_url(pdf_url):
    """Main function to process PDF and return results"""
    try:
        result = extract_pdf_info(pdf_url)

        if result:
            print("\nProcessing Summary:")
            print(f"File Hash: {result['file_256_hash']}")
            print(f"Total Pages: {result['images_in_doc'][0]['total_pages']}")

            total_images = sum(page["num_images"] for page in result["images_in_doc"])
            print(f"Total Images Found: {total_images}")

            # Print detailed page information
            for page in result["images_in_doc"]:
                if page["has_images"]:
                    print(f"\nPage {page['page_index'] + 1}:")
                    print(f"Number of Images: {page['num_images']}")
                    print("Image URLs:")
                    for url in page["image_urls"]:
                        print(f"  - {url}")

            # Print consolidated image URLs
            print("\nAll Image URLs:")
            for url in result["paper_image_urls"]:
                print(f"  - {url}")

            return result

    except Exception as e:
        print(f"Error in process_pdf_url: {str(e)}")
        return None

def read_pdf_from_url(pdf_url):
    try:
        # Convert Google Cloud Storage URL to direct download URL
        pdf_url = pdf_url.replace("storage.cloud.google.com", "storage.googleapis.com")

        # Download the PDF
        response = requests.get(pdf_url)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Create a temporary file to store the PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name

        # Use PyPDFLoader to load the PDF
        loader = PyPDFLoader(temp_path)

        # Load and split the document into pages
        pages = loader.load_and_split()

        # Extract text from all pages
        text_content = "\n\n".join([page.page_content for page in pages])

        return text_content

    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

def extract_images_and_metadata_from_pdf(pdf_url: str, bucket_name: str) -> dict:
    """
    Extracts images and metadata from a PDF file.

    Args:
    pdf_url (str): The URL of the PDF file.

    Returns:
    dict: A dictionary containing the extracted images, metadata, and additional details.

    Raises:
    Exception: If an error occurs during processing.

    Custom Functions Used:
    - get_file_hash: Calculates the hash of a file.
    - upload_to_gcs: Uploads a file to Google Cloud Storage and returns the URL.

    Note: This function requires the following modules: requests, fitz, os, tempfile.
    """
    try:
        # Convert GCS URL to direct download URL
        pdf_url = pdf_url.replace("storage.cloud.google.com", "storage.googleapis.com")

        # Create temporary directory for extracted images
        tmp_dir = "tmp_extracted_images"
        os.makedirs(tmp_dir, exist_ok=True)

        # Download PDF content
        response = requests.get(pdf_url)
        response.raise_for_status()
        pdf_content = response.content

        # Calculate file hash
        file_256_hash = get_file_hash(pdf_content)

        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name

        # Open PDF with PyMuPDF
        pdf_document = fitz.open(temp_path)
        total_pages = len(pdf_document)

        # Initialize result structure
        result = {
            "file_256_hash": file_256_hash,
            "images_in_doc": [],
            "paper_image_urls": [],
            "total_images": 0,  # Total number of images across all pages
            "page_details": []  # Detailed information about pages with images
        }

        # Process each page
        for page_num in range(total_pages):
            page = pdf_document[page_num]
            image_list = page.get_images()

            page_info = {
                "page_index": page_num,
                "total_pages": total_pages,
                "has_images": len(image_list) > 0,
                "num_images": len(image_list),
                "image_urls": []
            }

            # Extract images if they exist
            if image_list:
                for img_idx, img in enumerate(image_list, 1):
                    try:
                        # Get image data
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]

                        # Create filename
                        image_filename = f"extracted_img_{page_num + 1}_of_{img_idx}.jpeg"
                        local_path = os.path.join(tmp_dir, image_filename)

                        # Save locally
                        with open(local_path, "wb") as image_file:
                            image_file.write(image_bytes)

                        # Upload to GCS and get URL
                        image_url = upload_to_gcs(
                            image_content=image_bytes,
                            filename=image_filename,
                            file_hash=file_256_hash,
                            bucket_name=bucket_name # BUCKET_EXTRACTED_IMAGES
                        )

                        if image_url:
                            page_info["image_urls"].append(image_url)
                            result["paper_image_urls"].append(image_url)  # Add to consolidated list

                    except Exception as e:
                        print(f"Error processing image {img_idx} on page {page_num + 1}: {str(e)}")

            # Update total_images count
            result["total_images"] += page_info["num_images"]

            # Append detailed page info if images are present
            if page_info["has_images"]:
                result["page_details"].append({
                    "page_index": page_num,
                    "num_images": page_info["num_images"],
                    "image_urls": page_info["image_urls"]
                })

            result["images_in_doc"].append(page_info)

        # Cleanup
        pdf_document.close()
        os.unlink(temp_path)

        # Clean up temporary directory
        for file in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, file))
        os.rmdir(tmp_dir)

        return result

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return None
