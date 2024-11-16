
import os
import json
from google.cloud import storage
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
secret_json = os.getenv('GOOGLE_SECRET_JSON')

def save_file_to_bucket(artifact_url, session_id, sample_id, bucket_name, subdir="papers", subsubdirs=["pdf","word","images","csv","text"]):
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
            blob_prefix = f"{session_id}/{sample_id}/{subdir}/{subsubdir}/"
            bucket = client.bucket(bucket_name)
            blobs = client.list_blobs(bucket, prefix=blob_prefix)
            for blob in blobs:
                blob.delete()

    try:
        # Upload the file to Google Cloud Storage
        blob_name = f"{session_id}/{sample_id}/{subdir}/{subsubdir}/{os.path.basename(artifact_url)}"
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


def get_public_urls(bucket_name, session_id, sample_id):
    
    client = storage.Client.from_service_account_info(json.loads(secret_json))
    
    bucket = client.bucket(bucket_name)
    
    blobs = bucket.list_blobs(prefix=f"{session_id}/{sample_id}/")
    
    return [f"https://storage.googleapis.com/{bucket_name}/{blob.name}" for blob in blobs]