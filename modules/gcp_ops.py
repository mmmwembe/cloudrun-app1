
import os
import json
from google.cloud import storage
from dotenv import load_dotenv
import pandas as pd

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
secret_json = os.getenv('GOOGLE_SECRET_JSON')


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


def save_tracker_csv(df, session_id, bucket_name):
    """
    Save a pandas DataFrame as a CSV to the specified GCS bucket using session_id as filename.
    Uses the save_file_to_bucket function for GCS upload.
    
    Args:
        df (pandas.DataFrame): The DataFrame to save
        session_id (str): The session ID to use as filename
        bucket_name (str): The GCS bucket name where the CSV will be saved
    
    Returns:
        str or None: The public URL of the saved CSV file if successful, None if failed
    """
    try:
        # Create a temporary local CSV file
        temp_csv_path = os.path.join('static', 'tmp', f'{session_id}.csv')
        os.makedirs(os.path.dirname(temp_csv_path), exist_ok=True)
        
        # Save DataFrame to temporary CSV
        df.to_csv(temp_csv_path, index=False)
        
        # Use save_file_to_bucket to upload the CSV
        url = save_file_to_bucket(
            artifact_url=temp_csv_path,
            session_id=session_id,
            bucket_name=bucket_name
        )
        
        # Clean up temporary file
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
            
        return url
        
    except Exception as e:
        print(f"Error saving tracker CSV: {str(e)}")
        # Clean up temporary file in case of error
        if os.path.exists(temp_csv_path):
            os.remove(temp_csv_path)
        return None

def initialize_paper_upload_tracker_df_from_gcp(session_id, bucket_name):
    """
    Initialize a pandas DataFrame from a CSV file stored in GCS using session_id.
    Reads directly from GCS URL.
    
    Args:
        session_id (str): The session ID used as the CSV filename
        bucket_name (str): The GCS bucket name where the CSV is stored
    
    Returns:
        pandas.DataFrame: The initialized DataFrame, or an empty DataFrame with default columns if file not found
    """
    try:
        # Construct the GCS URL
        gcs_url = f"https://storage.googleapis.com/{bucket_name}/{session_id}/papers/csv/{session_id}.csv"
        
        # Read directly from URL
        df = pd.read_csv(gcs_url)
        return df
        
    except Exception as e:
        print(f"Error initializing DataFrame from GCS: {str(e)}")
        # If file doesn't exist or other error, return empty DataFrame with default columns
        return pd.DataFrame(columns=[
            'gcp_public_url',
            'hash',
            'original_filename',
            'citation_name',
            'citation_authors',
            'citation_year',
            'citation_organization',
            'citation_doi',
            'citation_url',
            'upload_timestamp',
            'processed',
        ])
 
# def initialize_tracker_df_from_gcp(session_id, bucket_name):
#     """
#     Initialize a pandas DataFrame from a CSV file stored in GCS using session_id.
    
#     Args:
#         session_id (str): The session ID used as the CSV filename
#         bucket_name (str): The GCS bucket name where the CSV is stored
    
#     Returns:
#         pandas.DataFrame: The initialized DataFrame, or an empty DataFrame with default columns if file not found
#     """
#     try:
#         # Initialize GCS client
#         client = storage.Client.from_service_account_info(json.loads(secret_json))
#         bucket = client.bucket(bucket_name)
        
#         # Construct blob path (matching the structure from save_file_to_bucket)
#         blob_name = f"{session_id}/papers/csv/{session_id}.csv"
#         blob = bucket.blob(blob_name)
        
#         # Create a temporary file to store the downloaded CSV
#         temp_csv_path = os.path.join('static', 'tmp', f'temp_{session_id}.csv')
#         os.makedirs(os.path.dirname(temp_csv_path), exist_ok=True)
        
#         # Download the blob to a temporary file
#         blob.download_to_filename(temp_csv_path)
        
#         # Read the CSV into a DataFrame
#         df = pd.read_csv(temp_csv_path)
        
#         # Clean up temporary file
#         if os.path.exists(temp_csv_path):
#             os.remove(temp_csv_path)
            
#         return df
        
#     except Exception as e:
#         print(f"Error initializing DataFrame from GCS: {str(e)}")
#         # If file doesn't exist or other error, return empty DataFrame with default columns
#         return pd.DataFrame(columns=[
#             'gcp_public_url',
#             'hash',
#             'original_filename',
#             'citation_name',
#             'citation_authors',
#             'citation_year',
#             'citation_organization',
#             'citation_doi',
#             'citation_url',
#             'upload_timestamp'
#         ])
#     finally:
#         # Ensure cleanup of temporary file
#         if 'temp_csv_path' in locals() and os.path.exists(temp_csv_path):
#             os.remove(temp_csv_path)    
            
            
# def save_file_to_bucket(artifact_url, session_id, file_hash_num, bucket_name, subdir="papers", subsubdirs=["pdf","word","images","csv","text"]):
#     # Determine the subsubdir based on the file extension
#     if artifact_url.endswith(".docx"):
#         subsubdir = "word"
#     elif artifact_url.endswith((".jpg", ".jpeg", ".png", ".gif")):
#         subsubdir = "images"
#     elif artifact_url.endswith(".csv"):
#         subsubdir = "csv"
#     elif artifact_url.endswith((".txt", ".text")):
#         subsubdir = "text"
#     else:
#         subsubdir = "pdf"  # Default to PDF if no other match

#     client = storage.Client.from_service_account_info(json.loads(secret_json))

#     if subsubdir == "word":
#             # Delete the contents of the subsubdir before uploading the new file
#             blob_prefix = f"{session_id}/{file_hash_num}/{subdir}/{subsubdir}/"
#             bucket = client.bucket(bucket_name)
#             blobs = client.list_blobs(bucket, prefix=blob_prefix)
#             for blob in blobs:
#                 blob.delete()

#     try:
#         # Upload the file to Google Cloud Storage
#         blob_name = f"{session_id}/{file_hash_num}/{subdir}/{subsubdir}/{os.path.basename(artifact_url)}"
#         bucket = client.bucket(bucket_name)
#         blob = bucket.blob(blob_name)
#         blob.upload_from_filename(artifact_url)
#         #print(f"File uploaded to: gs://{bucket_name}/{blob_name}")
#         url = blob.public_url
#         #print(f"Public URL: {url}")
#         return url
#     except Exception as e:
#         print("An error occurred:", e)
#         return None


def get_public_urls(bucket_name, session_id, file_hash_num):
    
    client = storage.Client.from_service_account_info(json.loads(secret_json))
    
    bucket = client.bucket(bucket_name)
    
    blobs = bucket.list_blobs(prefix=f"{session_id}/{file_hash_num}/")
    
    return [f"https://storage.googleapis.com/{bucket_name}/{blob.name}" for blob in blobs]


def get_public_urls2(bucket_name, session_id, file_hash_num):
    client = storage.Client.from_service_account_info(json.loads(secret_json))
    bucket = client.bucket(bucket_name)
    
    blobs = bucket.list_blobs(prefix=f"{session_id}/{file_hash_num}/")
    
    files = []
    for blob in blobs:
        file_info = {
            'name': blob.name.split('/')[-1],  # File name
            'blob_name': blob.name,  # Full blob name
            'size': f"{blob.size / 1024 / 1024:.2f} MB",  # Size in MB
            'updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),  # Last updated timestamp
            'public_url': f"https://storage.googleapis.com/{bucket_name}/{blob.name}"  # Public URL
        }
        files.append(file_info)
    
    return files


def save_json_to_bucket(local_file_path, bucket_name, session_id):
    """
    Save a local JSON file to a GCP bucket in the format {bucket_name}/labels/{session_id}/{session_id}.json.

    Args:
        local_file_path (str): The path to the local file to upload.
        bucket_name (str): The name of the GCP bucket.
        session_id (str): The session ID used to define the file structure.

    Returns:
        tuple: (blob_name, public_url) where blob_name is the path in the bucket and public_url is the public URL of the uploaded file.
    """
    try:
        # Initialize the GCP storage client
        client = storage.Client.from_service_account_info(json.loads(secret_json))
        bucket = client.bucket(bucket_name)

        # Create the full path in the bucket
        blob_name = f"labels/{session_id}/{session_id}.json"
        blob = bucket.blob(blob_name)

        # Upload the file
        blob.upload_from_filename(local_file_path)

        # Generate the public URL
        public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

        return public_url
    except Exception as e:
        print(f"Error uploading file to bucket '{bucket_name}': {e}")
        return None, None
    
    #save_json_to_bucket(local_file_path, bucket_name, session_id)
    #public_url = f"https://storage.googleapis.com/{bucket_name}/labels/{SESSION_ID}/{SESSION_ID}.json"