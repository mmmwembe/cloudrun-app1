# Import necessary modules
import os
import hashlib
import tempfile
import requests
import fitz  # PyMuPDF
from google.cloud import storage
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
secret_json = os.getenv('GOOGLE_SECRET_JSON')

def get_storage_client():
    """Get authenticated GCS client"""
    return storage.Client.from_service_account_info(json.loads(secret_json))

# Function to calculate SHA-256 hash
def get_file_hash(file_content):
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()

# Function to upload an image to GCS and return its public URL
def upload_to_gcs(image_content, filename, session_id, bucket_name):
    """Upload image to Google Cloud Storage and return public URL"""
    try:
        client = get_storage_client()
        bucket = client.bucket(bucket_name)

        # Create blob path using session ID and file hash
        blob_path = f"{session_id}/{filename}"
        blob = bucket.blob(blob_path)

        # Upload image
        blob.upload_from_string(image_content, content_type='image/jpeg')

        # Generate public URL
        public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
        return public_url

    except Exception as e:
        print(f"Error uploading to GCS: {str(e)}")
        return None

# Function to extract images and metadata from a PDF
def extract_images_and_metadata_from_pdf(pdf_url: str, session_id: str, bucket_name: str) -> dict:
    """
    Extracts images and metadata from a PDF file.
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
            "total_images": 0,
            "page_details": []
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

            if image_list:
                for img_idx, img in enumerate(image_list, 1):
                    try:
                        # Get image data
                        xref = img[0]
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]

                        # Create filename 
                        #image_filename = f"extracted_img_{page_num + 1}_of_{img_idx}.jpeg"
                        image_filename = f"{file_256_hash}_image_{img_idx}.jpeg"

                        # Upload to GCS and get URL
                        image_url = upload_to_gcs(
                            image_content=image_bytes,
                            filename=image_filename,
                            session_id=session_id,
                            bucket_name=bucket_name
                        )

                        if image_url:
                            page_info["image_urls"].append(image_url)
                            result["paper_image_urls"].append(image_url)

                    except Exception as e:
                        print(f"Error processing image {img_idx} on page {page_num + 1}: {str(e)}")

            # Update total_images count
            result["total_images"] += page_info["num_images"]

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
        for file in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, file))
        os.rmdir(tmp_dir)

        return result

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return None

# # URL of the PDF file
# pdf_url = "https://storage.googleapis.com/papers-diatoms/pdf/eb9db0ca54e94dbc82cffdab497cde13/5_Azores.pdf"

# # Call the function
# BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
# SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
# result = extract_images_and_metadata_from_pdf(pdf_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
# # Convert the result dictionary to a JSON string
# result_string = json.dumps(result, indent=4)

