import pandas as pd
import os
from google.cloud import storage
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

# Get the Google service account JSON from environment variable
secret_json = os.getenv('GOOGLE_SECRET_JSON')

def get_storage_client():
    """Get authenticated GCS client"""
    return storage.Client.from_service_account_info(json.loads(secret_json))

def save_df_to_gcs(df: pd.DataFrame, bucket_name: str, session_id: str) -> str:
    """
    Save a Pandas DataFrame to a GCS bucket as a CSV file and return its public URL.

    Args:
        df (pd.DataFrame): The DataFrame to save.
        bucket_name (str): The name of the GCS bucket.
        session_id (str): A unique session identifier used for the file path and name.

    Returns:
        str: The public URL of the saved CSV file in the GCS bucket.
    """
    try:
        # Ensure GCS client is authenticated
        client = get_storage_client()

        # Create CSV file name and path in the bucket
        csv_filename = f"{session_id}.csv"
        blob_path = f"csv/{session_id}/{csv_filename}"

        # Save DataFrame to a temporary CSV file locally
        temp_csv_path = f"{csv_filename}"
        df.to_csv(temp_csv_path, index=False)

        # Get the GCS bucket
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        # Upload the CSV file to GCS
        blob.upload_from_filename(temp_csv_path, content_type="text/csv")

        # Make the file publicly accessible
        blob.make_public()

        # Clean up the local temporary CSV file
        os.remove(temp_csv_path)

        # Return the public URL of the uploaded file
        public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
        return public_url

    except Exception as e:
        print(f"Error saving DataFrame to GCS: {e}")
        return None

def load_or_initialize_df(bucket_name: str, session_id: str) -> pd.DataFrame:
    """
    Loads a DataFrame from a CSV file stored in a GCS bucket or initializes a new one
    if the file does not exist.

    Args:
        bucket_name (str): The name of the GCS bucket.
        session_id (str): The unique session ID used to identify the CSV file.

    Returns:
        pd.DataFrame: The DataFrame either loaded from the CSV or initialized with default columns.
    """
    try:
        # Initialize GCS client
        client = get_storage_client()

        # Construct the blob path for the CSV file in the bucket
        csv_filename = f"{session_id}.csv"
        blob_path = f"csv/{session_id}/{csv_filename}"

        # Get the GCS bucket
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        # Check if the file exists
        if blob.exists():
            # If file exists, download it and load into DataFrame
            print(f"File found in GCS bucket. Loading CSV file from {blob_path}")
            # Download the file as a string and read it into a DataFrame
            df = pd.read_csv(blob.download_as_text())
        else:
            # If file does not exist, initialize the DataFrame with default columns
            print(f"File not found in GCS bucket. Initializing new DataFrame.")
            df = pd.DataFrame(columns=[
                'gcp_public_url', 'original_filename', 'pdf_text_content', 'file_256_hash',
                'citation_name', 'citation_authors', 'citation_year', 'citation_organization', 'citation_doi',
                'citation_url', 'upload_timestamp', 'processed', 'images_in_doc', 'paper_image_urls',
                'species_id', 'species_index', 'species_name', 'species_authors', 'species_year',
                'species_references', 'formatted_species_name', 'genus', 'species_magnification',
                'species_scale_bar_microns', 'species_note', 'figure_caption', 'source_material_location',
                'source_material_coordinates', 'source_material_description', 'source_material_received_from',
                'source_material_date_received', 'source_material_note', 'cropped_image_url', 'embeddings_256',
                'embeddings_512', 'embeddings_1024', 'embeddings_2048', 'embeddings_4096', 
                'bbox_top_left_bottom_right', 'yolo_bbox', 'segmentation'
            ]).astype({
                'gcp_public_url': 'str', 'original_filename': 'str', 'pdf_text_content': 'str',
                'file_256_hash': 'str', 'citation_name': 'str', 'citation_authors': 'str',
                'citation_year': 'str', 'citation_organization': 'str', 'citation_doi': 'str',
                'citation_url': 'str', 'upload_timestamp': 'datetime64[ns]', 'processed': 'bool',
                'images_in_doc': 'object', 'paper_image_urls': 'object', 'species_id': 'str',
                'species_index': 'str', 'species_name': 'str', 'species_authors': 'object',
                'species_year': 'str', 'species_references': 'object', 'formatted_species_name': 'str',
                'genus': 'str', 'species_magnification': 'str', 'species_scale_bar_microns': 'str',
                'species_note': 'str', 'figure_caption': 'str', 'source_material_location': 'str',
                'source_material_coordinates': 'str', 'source_material_description': 'str',
                'source_material_received_from': 'str', 'source_material_date_received': 'str',
                'source_material_note': 'str', 'cropped_image_url': 'str', 'embeddings_256': 'object',
                'embeddings_512': 'object', 'embeddings_1024': 'object', 'embeddings_2048': 'object',
                'embeddings_4096': 'object', 'bbox_top_left_bottom_right': 'str', 'yolo_bbox': 'str',
                'segmentation': 'str'
            })
        
        return df

    except Exception as e:
        print(f"Error loading or initializing DataFrame: {e}")
        return None


