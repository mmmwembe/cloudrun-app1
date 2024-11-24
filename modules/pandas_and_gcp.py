import pandas as pd
import os
from google.cloud import storage
from dotenv import load_dotenv
import json
import uuid
from modules.pdf_image_and_metadata_handler import extract_images_and_metadata_from_pdf
from modules.utils import extract_text_from_pdf
from modules.llm_ops import llm_parsed_output_from_text, create_messages, llm_with_JSON_output

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

def load_or_initialize_processed_files_df(bucket_name: str, session_id: str) -> pd.DataFrame:
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


def update_processed_files_df_tracking(public_url, citation, session_id, extracted_images_bucket_name,PROCESSED_FILES_PD):
    """
    Update the PROCESSED_FILES_PD DataFrame with file information and citation details.
    Extracts filename from the public_url and processes the PDF to update additional fields.

    Args:
        public_url (str): The public URL from GCP storage.
        citation (dict): Citation information for the document.
        session_id (str): The session ID for tracking.
        extracted_images_bucket_name (str): The bucket where extracted images will be stored.

    Returns:
        tuple: (filename, citation, result, pdf_text_content, parsed_output)
    """
    #global PROCESSED_FILES_PD

    # Extract filename from the public_url
    filename = public_url.split('/')[-1]

    # Process the PDF and get details
    result = extract_images_and_metadata_from_pdf(public_url, session_id, extracted_images_bucket_name)
    print("-----------------result---------------")
    # Extract information from the result
    file_256_hash = result.get('file_256_hash', '')
    images_in_doc = result.get('images_in_doc', [])
    paper_image_urls = result.get('paper_image_urls', [])

    # Extract all text from the pdf
    pdf_text_content = extract_text_from_pdf(public_url)

    # Get dictionary of LLM output
    parsed_output = llm_with_JSON_output(pdf_text_content)

    # Set variables for source material and species (with default empty values)
    figure_caption = parsed_output.get('figure_caption', '')
    source_material_location = parsed_output.get('source_material_location', '')
    source_material_coordinates = parsed_output.get('source_material_coordinates', '')
    source_material_description = parsed_output.get('source_material_description', '')
    source_material_received_from = parsed_output.get('source_material_received_from', '')
    source_material_date_received = parsed_output.get('source_material_date_received', '')
    source_material_note = parsed_output.get('source_material_note', '')

    # Default to processed as False unless species are found
    processed = False
    species_index, species_name, species_authors, species_year, species_references, formatted_species_name, genus, species_magnification, species_scale_bar_microns, species_note = '', '', [], '', [], '', '', '', '', ''

    # Iterate through species array and update variables
    for species in parsed_output.get('diatom_species_array', []):
        species_index = species.get('species_index', '')
        species_name = species.get('species_name', '')
        species_authors = species.get('species_authors', [])
        species_year = species.get('species_year', '')
        species_references = species.get('species_references', [])
        formatted_species_name = species.get('formatted_species_name', '')
        genus = species.get('genus', '')
        species_magnification = species.get('species_magnification', '')
        species_scale_bar_microns = species.get('species_scale_bar_microns', '')
        species_note = species.get('species_note', '')
        processed = True  # Set processed to True when species are found

    # Create new row data with default empty values
    new_row = {
        # File and URL information
        'gcp_public_url': public_url,
        'original_filename': filename,
        'pdf_text_content': pdf_text_content,
        'file_256_hash': file_256_hash,

        # Citation information
        'citation_name': citation.get('name', ''),
        'citation_authors': ', '.join(citation.get('authors', [])),
        'citation_year': citation.get('year', ''),
        'citation_organization': citation.get('organization', ''),
        'citation_doi': citation.get('doi', ''),
        'citation_url': citation.get('url', ''),

        # Processing status
        'upload_timestamp': pd.Timestamp.now(),
        'processed': processed,

        # Image information
        'images_in_doc': images_in_doc,
        'paper_image_urls': paper_image_urls,

        # Species information
        'species_id': uuid.uuid4().hex,
        'species_index': species_index,
        'species_name': species_name,
        'species_authors': species_authors,
        'species_year': species_year,
        'species_references': species_references,
        'formatted_species_name': formatted_species_name,
        'genus': genus,
        'species_magnification': species_magnification,
        'species_scale_bar_microns': species_scale_bar_microns,
        'species_note': species_note,

        # Source material information
        'figure_caption': figure_caption,
        'source_material_location': source_material_location,
        'source_material_coordinates': source_material_coordinates,
        'source_material_description': source_material_description,
        'source_material_received_from': source_material_received_from,
        'source_material_date_received': source_material_date_received,
        'source_material_note': source_material_note,

        # Cropped image, embeddings, bounding boxes and segmentation
        'cropped_image_url': "",
        'embeddings_256':  [],
        'embeddings_512':  [],
        'embeddings_1024': [],
        'embeddings_2048': [],
        'embeddings_4096': [],
        'bbox_top_left_bottom_right': "",
        'yolo_bbox': "",
        'segmentation': ""
    }

    # Add new row to DataFrame
    new_df = pd.DataFrame([new_row])
    for col in PROCESSED_FILES_PD.columns:
        new_df[col] = new_df[col].astype(PROCESSED_FILES_PD[col].dtype)
    PROCESSED_FILES_PD = pd.concat([PROCESSED_FILES_PD, new_df], ignore_index=True)

    try:
        # Save updated DataFrame to GCS (commented out as an example)
        pass
    except Exception as e:
        print(f"Error saving tracking data to GCS: {e}")

    # Return the required values
    return filename, citation, result, pdf_text_content, parsed_output, PROCESSED_FILES_PD

# filename, citation, result, pdf_text_content, parsed_output = update_processed_files_df_tracking(
#     public_url,
#     citation,
#     SESSION_ID,
#     BUCKET_EXTRACTED_IMAGES
# )

# def update_processed_files_df_tracking(public_url, citation, session_id, extracted_images_bucket_name):
#     """
#     Update the PARENT_FILES_PD DataFrame with file information and citation details.
#     Extracts filename from the public_url and processes the PDF to update additional fields.

#     Args:
#         public_url (str): The public URL from GCP storage.

#     Returns:
#         tuple: (filename, citation, result, pdf_text_content, parsed_output)
#     """
#     global PROCESSED_FILES_PD

#     # Extract filename from the public_url
#     filename = public_url.split('/')[-1]

#     # Get default citation info
#     # citation = get_default_citation()

#     # Process the PDF and get details
#     result = extract_images_and_metadata_from_pdf(public_url, session_id, extracted_images_bucket_name)
#     print("-----------------result---------------")
#     #print(result)
#     # Extract information from the result
#     file_256_hash = result.get('file_256_hash', '')
#     images_in_doc = result.get('images_in_doc', [])
#     paper_image_urls = result.get('paper_image_urls', [])

#     # Extract all text from the pdf
#     pdf_text_content = extract_text_from_pdf(public_url)

#     # Get dictionary of LLM output
#     parsed_output = llm_with_JSON_output(pdf_text_content)
#     #print("-----------------parsed output---------------")
#     #print(parsed_output)

#     # Set variables
#     figure_caption = parsed_output.get('figure_caption', '')
#     source_material_location = parsed_output.get('source_material_location', '')
#     source_material_coordinates = parsed_output.get('source_material_coordinates', '')
#     source_material_description = parsed_output.get('source_material_description', '')
#     source_material_received_from = parsed_output.get('source_material_received_from', '')
#     source_material_date_received = parsed_output.get('source_material_date_received', '')
#     source_material_note = parsed_output.get('source_material_note', '')

#     processed = False

#     # Iterate through species array
#     #print("\nSpecies Information:")
#     for species in parsed_output.get('diatom_species_array', []):
#         species_index = species.get('species_index', '')
#         species_name = species.get('species_name', '')
#         species_authors = species.get('species_authors', [])
#         species_year = species.get('species_year', '')
#         species_references = species.get('species_references', [])
#         formatted_species_name = species.get('formatted_species_name', '')
#         genus = species.get('genus', '')
#         species_magnification = species.get('species_magnification', '')
#         species_scale_bar_microns = species.get('species_scale_bar_microns', '')
#         species_note = species.get('species_note', '')
#         processed = True

#         # print(f"\nSpecies {species_index}:")
#         # print("Name:", species_name)
#         # print("Authors:", species_authors)
#         # print("Year:", species_year)
#         # print("References:", species_references)
#         # print("Formatted Name:", formatted_species_name)
#         # print("Genus:", genus)
#         # print("Magnification:", species_magnification)
#         # print("Scale Bar (microns):", species_scale_bar_microns)
#         # print("Note:", species_note)

#     # Create new row data with default empty values
#     new_row = {
#         # File and URL information
#         'gcp_public_url': public_url,
#         'original_filename': filename,
#         'pdf_text_content': pdf_text_content,
#         'file_256_hash': file_256_hash,

#         # Citation information
#         'citation_name': citation.get('name', ''),
#         'citation_authors': ', '.join(citation.get('authors', [])),
#         'citation_year': citation.get('year', ''),
#         'citation_organization': citation.get('organization', ''),
#         'citation_doi': citation.get('doi', ''),
#         'citation_url': citation.get('url', ''),

#         # Processing status
#         'upload_timestamp': pd.Timestamp.now(),
#         'processed': processed,

#         # Image information
#         'images_in_doc': images_in_doc,
#         'paper_image_urls': paper_image_urls,

#         # Species information
#         'species_id': uuid.uuid4().hex,
#         'species_index': species_index,
#         'species_name': species_name,
#         'species_authors': species_authors,
#         'species_year': species_year,
#         'species_references': species_references,
#         'formatted_species_name': formatted_species_name,
#         'genus': genus,
#         'species_magnification': species_magnification,
#         'species_scale_bar_microns': species_scale_bar_microns,
#         'species_note': species_note,

#         # Source material information
#         'figure_caption': figure_caption,
#         'source_material_location': source_material_location,
#         'source_material_coordinates': source_material_coordinates,
#         'source_material_description': source_material_description,
#         'source_material_received_from': source_material_received_from,
#         'source_material_date_received': source_material_date_received,
#         'source_material_note': source_material_note,

#         # Cropped image, embeddings, bounding boxes and segmentation
#         'cropped_image_url': "",
#         'embeddings_256':  [],
#         'embeddings_512':  [],
#         'embeddings_1024': [],
#         'embeddings_2048': [],
#         'embeddings_4096': [],
#         'bbox_top_left_bottom_right': "",
#         'yolo_bbox': "",
#         'segmentation': ""
#     }

#     # Add new row to DataFrame
#     new_df = pd.DataFrame([new_row])
#     for col in PROCESSED_FILES_PD.columns:
#         new_df[col] = new_df[col].astype(PROCESSED_FILES_PD[col].dtype)
#     PROCESSED_FILES_PD = pd.concat([PROCESSED_FILES_PD, new_df], ignore_index=True)

#     try:
#         # Save updated DataFrame to GCS (commented out as an example)
#         pass
#     except Exception as e:
#         print(f"Error saving tracking data to GCS: {e}")

#     # Return the required values
#     return filename, citation, result, pdf_text_content, parsed_output
