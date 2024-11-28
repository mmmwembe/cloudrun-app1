# app.py
import os
from flask import Flask, render_template, request, flash, redirect, url_for, Response, jsonify, send_file
from werkzeug.utils import secure_filename
from google.cloud import storage
import json
from dotenv import load_dotenv
import pandas as pd
from modules.process_pdfs import process_pdf
from modules.claude_ai import create_claude_prompt, encode_pdf_to_base64, create_messages, get_completion
# from modules.groq_llama import get_llama_paper_info
from modules.gcp_ops import save_file_to_bucket, save_tracker_csv, initialize_paper_upload_tracker_df_from_gcp, save_json_to_bucket, save_paper_json_files, load_paper_json_files
# save_file_to_bucket(artifact_url, session_id, file_hash_num, bucket_name, subdir="papers"
from datetime import datetime
# from modules.llm_ops import llm_parsed_output_from_text, create_messages, llm_with_JSON_output
from modules.pdf_image_and_metadata_handler import extract_images_and_metadata_from_pdf
from modules.pandas_and_gcp import save_df_to_gcs, load_or_initialize_processed_files_df, update_processed_files_df_tracking
from modules.process_files_df import update_process_files_pd, PROCESS_FILES_PD, validate_update_arguments
import requests
# from langchain_community.document_loaders import PyPDFLoader
import tempfile
from modules.utils import extract_text_from_pdf
import time
import uuid
import traceback

load_dotenv()

app = Flask(__name__)
app.secret_key = b'\xcc^\x91\xea\x17-\xd0W\x03\xa7\xf8J0\xac8\xc5'
app.config['SECURITY_PASSWORD_SALT'] = 'thisistheSALTforcreatingtheCONFIRMATIONtoken'
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # Increased to 64MB for multiple files
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Configure constants
BUCKET_NAME = 'papers-bucket-mmm'
# Configure bucket names
BUCKET_ORIGINAL_PAPERS = 'papers-parent-bucket-mmm'
BUCKET_SPLIT_PAGES = 'papers-split-pages-bucket-mmm'
BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
BUCKET_PAPER_TRACKER_CSV = 'papers-extracted-pages-csv-bucket-mmm'
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
FILE_HASH_NUM = '8c583173bc904ce596d5de69ac432acb'
PAPERS_BUCKET ='papers-diatoms'
PAPERS_PROCESSED_BUCKET ='papers-diatoms-processed'
PAPERS_BUCKET_LABELLING ='papers-diatoms-labelling'
PAPERS_BUCKET_JSON_FILES ='papers-diatoms-jsons'

ALLOWED_EXTENSIONS = {'pdf'}

test_pdf_path = os.path.join("static", "test-pdf", "3_Azores.pdf")
workflow_image_path = os.path.join("static", "pdf-work-flow", "mermaid-diagram-worfklow.svg")

formatted_date = datetime.now().strftime("%m-%d-%y")
# print(formatted_date)

# Initialize temp directories
TEMP_EXTRACTED_PDFS_DIR = os.path.join(app.static_folder, 'tmp_extracted_pdfs')
os.makedirs(TEMP_EXTRACTED_PDFS_DIR, exist_ok=True)

TEMP_EXTRACTED_IMAGES_DIR = os.path.join(app.static_folder, 'tmp_extracted_images')
os.makedirs(TEMP_EXTRACTED_IMAGES_DIR, exist_ok=True)


# def read_pdf_from_url(pdf_url):
#     try:
#         # Convert Google Cloud Storage URL to direct download URL
#         pdf_url = pdf_url.replace("storage.cloud.google.com", "storage.googleapis.com")

#         # Download the PDF
#         response = requests.get(pdf_url)
#         response.raise_for_status()  # Raise an exception for bad status codes

#         # Create a temporary file to store the PDF
#         with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
#             temp_file.write(response.content)
#             temp_path = temp_file.name

#         # Use PyPDFLoader to load the PDF
#         loader = PyPDFLoader(temp_path)

#         # Load and split the document into pages
#         pages = loader.load_and_split()

#         # Extract text from all pages
#         text_content = "\n\n".join([page.page_content for page in pages])

#         return text_content

#     except Exception as e:
#         print(f"Error reading PDF: {e}")
#         return None


# Initialize global parent files DataFrame
# PARENT_FILES_PD = pd.DataFrame(columns=[
#     'gcp_public_url',
#     'hash',
#     'original_filename',
#     'citation_name',
#     'citation_authors',
#     'citation_year',
#     'citation_organization',
#     'citation_doi',
#     'citation_url',
#     'upload_timestamp'
# ])

# PARENT_FILES_PD = initialize_tracker_df_from_gcp(session_id=SESSION_ID,bucket_name=BUCKET_PAPER_TRACKER_CSV)

# Initialize df tracker for the uploaded files (before being processed)
# updating this df is made with update_uploaded_files_tracking(public_url)
# Update of this df is performed in @app.route('/', methods=['GET', 'POST']) route
# Saving of this df to GCP is perfomred in update_uploaded_files_tracking(public_url) with save_tracker_csv(PARENT_FILES_PD, SESSION_ID, BUCKET_PAPER_TRACKER_CSV)
PARENT_FILES_PD = initialize_paper_upload_tracker_df_from_gcp(session_id=SESSION_ID,bucket_name=BUCKET_PAPER_TRACKER_CSV) #

# Initialize df tracker for processed pdf files 
# Update of PD is made with update_processed_files_df_tracking(public_url, citation, session_id, extracted_images_bucket_name)
# Update of this df is performed in @app.route('/process_files/', methods=['POST']) route
# Saving of this df to GCP is performed in route('/process_files/', methods=['POST']) route with save_df_to_gcs(PROCESSED_FILES_PD, PAPERS_PROCESSED_BUCKET, SESSION_ID) 
# global PROCESSED_FILES_PD
# PROCESSED_FILES_PD = load_or_initialize_processed_files_df(session_id=SESSION_ID,bucket_name=PAPERS_PROCESSED_BUCKET)

def safe_value(value):
    return value if value else ""

def initialize_or_load_processed_files_df2(public_url: str) -> pd.DataFrame:
    """
    Tries to load the DataFrame from a public URL. If it fails, initializes a new one with default columns.

    Args:
        public_url (str): The public URL of the CSV file.

    Returns:
        pd.DataFrame: The loaded or initialized DataFrame.
    """
    try:
        # Attempt to load the DataFrame from the public URL
        print(f"Attempting to load DataFrame from: {public_url}")
        df = pd.read_csv(public_url)
        print("DataFrame successfully loaded.")
    except Exception as e:
        # Handle errors (e.g., file not found) by initializing a new DataFrame
        print(f"Error loading DataFrame from {public_url}: {e}")
        print("Initializing a new DataFrame.")
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
        ])
    
    return df


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


def update_uploaded_files_tracking(public_url):
    """
    Update the PARENT_FILES_PD DataFrame with file information and citation details.
    Extracts filename from the public_url.
    
    Args:
        public_url (str): The public URL from GCP storage
    """
    global PARENT_FILES_PD
    
    # Extract filename from the public_url
    filename = public_url.split('/')[-1]  # Gets the last part of the URL path (the filename)
    
    # Get default citation info
    citation = get_default_citation()
    
    # Create new row data
    new_row = {
        'gcp_public_url': public_url,
        'hash': FILE_HASH_NUM,
        'original_filename': filename,  # Using filename extracted from URL
        'citation_name': citation['name'],
        'citation_authors': ', '.join(citation['authors']),
        'citation_year': citation['year'],
        'citation_organization': citation['organization'],
        'citation_doi': citation['doi'],
        'citation_url': citation['url'],
        'upload_timestamp': pd.Timestamp.now(),
        'processed': False
    }
    
    # Add new row to DataFrame
    PARENT_FILES_PD = pd.concat([PARENT_FILES_PD, pd.DataFrame([new_row])], ignore_index=True)
    
    try:
        # Save updated DataFrame to GCS
        save_tracker_csv(PARENT_FILES_PD, SESSION_ID, BUCKET_PAPER_TRACKER_CSV)
        # save_df_to_gcs(PARENT_FILES_PD, SESSION_ID, PAPERS_BUCKET)

    except Exception as e:
        print(f"Error saving tracking data to GCS: {e}")



UPLOAD_DIR = os.path.join(os.getcwd(), 'temp_uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_storage_client():
    secret_json = os.getenv('GOOGLE_SECRET_JSON')
    return storage.Client.from_service_account_info(json.loads(secret_json))

def save_file_to_bucket(local_file_path, filename):
    try:
        client = get_storage_client()
        # bucket = client.bucket(BUCKET_NAME)
        bucket = client.bucket(PAPERS_BUCKET)        

        # Create the full path in the bucket
        blob_name = f"pdf/{SESSION_ID}/{filename}"
        blob = bucket.blob(blob_name)
        
        # Upload the file
        blob.upload_from_filename(local_file_path)
        
        public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET}/{blob_name}"
        
        return blob_name, public_url
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

def save_csv_to_bucket_v2(local_file_path, bucket_name, session_id):
    """
    Save a local CSV file to a GCP bucket in the format {bucket_name}/csv/{session_id}/{session_id}.csv.

    Args:
        local_file_path (str): The path to the local file to upload.
        bucket_name (str): The name of the GCP bucket.
        session_id (str): The session ID used to define the file structure.

    Returns:
        tuple: (blob_name, public_url) where blob_name is the path in the bucket and public_url is the public URL of the uploaded file.
    """
    try:
        # Initialize the GCP storage client
        client = get_storage_client()
        bucket = client.bucket(bucket_name)

        # Create the full path in the bucket
        blob_name = f"csv/{session_id}/{session_id}.csv"
        blob = bucket.blob(blob_name)

        # Upload the file
        blob.upload_from_filename(local_file_path)

        # Generate the public URL
        public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

        return public_url
    except Exception as e:
        print(f"Error uploading file to bucket '{bucket_name}': {e}")
        return None, None


def get_uploaded_files():
    try:
        client = get_storage_client()
        #bucket = client.bucket(BUCKET_NAME)
        bucket = client.bucket(PAPERS_BUCKET)
                
        # List all blobs in the PDF directory
        prefix = f"pdf/{SESSION_ID}/"
        blobs = bucket.list_blobs(prefix=prefix)
        
        # Get file information
        files = []
        for blob in blobs:
            file_info = {
                'name': blob.name.split('/')[-1],
                'blob_name': blob.name,
                'size': f"{blob.size / 1024 / 1024:.2f} MB",
                'updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),
                'public_url': f"https://storage.googleapis.com/{PAPERS_BUCKET}/{blob.name}" 
            }
            files.append(file_info)
        
        return sorted(files, key=lambda x: x['updated'], reverse=True)
    except Exception as e:
        print(f"Error listing files: {e}")
        return []

@app.route('/view_pdf/<path:blob_name>')
def view_pdf(blob_name):
    try:
        # Get the blob
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        # Download the PDF content
        content = blob.download_as_bytes()
        
        # Return the PDF in an inline content disposition
        return Response(
            content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'inline; filename=' + blob_name.split('/')[-1]
            }
        )
    except Exception as e:
        flash(f'Error viewing PDF: {str(e)}')
        return redirect(url_for('upload_file'))

@app.route('/preview_pdf/<path:blob_name>')
def preview_pdf(blob_name):
    """Render a page to preview the PDF"""
    return render_template('pdf_viewer.html', pdf_url=url_for('view_pdf', blob_name=blob_name))

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if any file was uploaded
        if 'files[]' not in request.files:
            flash('No files selected')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        
        if not files or all(file.filename == '' for file in files):
            flash('No files selected')
            return redirect(request.url)
        
        upload_count = 0
        error_count = 0
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                try:
                    file.save(temp_path)
                    blob_name, public_url = save_file_to_bucket(temp_path, filename)
                    #file_public_url = save_file_to_bucket(temp_path, SESSION_ID, FILE_HASH_NUM, BUCKET_NAME, subdir="papers")
                    
                    # Update PARENT_FILES_PD
                    update_uploaded_files_tracking(public_url)
                    
                    os.remove(temp_path)
                    
                    if blob_name:
                        upload_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"Error processing file {filename}: {e}")
                    error_count += 1
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                error_count += 1
        
        if upload_count > 0:
            flash(f'Successfully uploaded {upload_count} file(s)')
        if error_count > 0:
            flash(f'Failed to upload {error_count} file(s)')
        
        return redirect(url_for('upload_file'))

    files = get_uploaded_files()
    #files = get_public_urls2(BUCKET_NAME, SESSION_ID, FILE_HASH_NUM)
    return render_template('upload_images.html', files=files)



@app.route('/goto_processfile/')
def go_to_processfile():
    
    # num_rows = len(PARENT_FILES_PD)
    # Get DataFrame from GCS
    df = initialize_paper_upload_tracker_df_from_gcp(
        session_id=SESSION_ID,
        bucket_name=BUCKET_PAPER_TRACKER_CSV
    )
    
    # Get number of rows
    num_rows = len(df)  # or df.shape[0]
    
    return render_template('process_file.html', number_of_files=num_rows, session_id=SESSION_ID)

# @app.route('/process_files/', methods=['POST'])
# def process_files():
    
#     current_index = int(request.json.get('index', 0))
    
#     if current_index >= len(PARENT_FILES_PD):
#         return jsonify({'done': True})
        
#     current_file = PARENT_FILES_PD.iloc[current_index]
    
#     public_url = current_file['gcp_public_url']
    
#         # Extract filename from the public_url
#     filename = public_url.split('/')[-1]

#     # Get Info
#     citation = get_default_citation()
#     result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
#     pdf_text_content= extract_text_from_pdf(public_url)
#     llm_json_output = llm_with_JSON_output(pdf_text_content)
    
    
#     citation_string = json.dumps(citation, indent=4) 
#     result_string = json.dumps(result, indent=4)
#     extracted_text_str = str(pdf_text_content)
#     llm_json_output_string = json.dumps(llm_json_output) 
    
#     PROCESSED_FILES_PD = load_or_initialize_processed_files_df(session_id=SESSION_ID,bucket_name=PAPERS_PROCESSED_BUCKET)
    
#     # This updates PROCESSED_FILES_PD
#     filename, citation, result, pdf_text_content, llm_json_output, PROCESSED_FILES_PD = update_processed_files_df_tracking(public_url, citation, SESSION_ID, BUCKET_EXTRACTED_IMAGES,PROCESSED_FILES_PD)

    
#     # Save PD
#     # processed_files_csv_url = f"https://storage.googleapis.com/{PAPERS_PROCESSED_BUCKET}/csv/{SESSION_ID}/{SESSION_ID}.csv"
#     processed_files_csv_url = save_df_to_gcs(PROCESSED_FILES_PD, PAPERS_PROCESSED_BUCKET, SESSION_ID) 
    
#     time.sleep(65)
    
    
#     # TO-DO: UPDATE PARENT_FILES_PD 
    

#     return jsonify({
#         'done': False,
#         'gcp_public_url': current_file['gcp_public_url'],
#         'current_index': current_index,
#         'total_files': len(PARENT_FILES_PD),
#         'extracted_text': extracted_text_str,
#         'llm_json_output': llm_json_output_string,
#         'result_string': result_string,
#         'citation': citation_string,
#         'processed_files_csv_url': processed_files_csv_url,
#     })


# @app.route('/process_files/', methods=['POST'])
# def process_files():
#     try:
#         # Get the current index from the request body
#         current_index = int(request.json.get('index', 0))
        
#         # Check if the index exceeds the length of the DataFrame
#         if current_index >= len(PARENT_FILES_PD):
#             return jsonify({'done': True}), 200
            
#         # Get the current file from the DataFrame
#         current_file = PARENT_FILES_PD.iloc[current_index]
        
#         # Extract necessary information from the current file
#         public_url = current_file['gcp_public_url']
#         filename = public_url.split('/')[-1]

#         # Get the citation (you may have to adjust this method based on how you handle citation)
#         citation = get_default_citation()

#         # Extract additional information: result, pdf text, and LLM output
#         result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
#         pdf_text_content = extract_text_from_pdf(public_url)
#         llm_json_output = llm_with_JSON_output(pdf_text_content)
#         papers_json_public_url =''

#         # Validate arguments before proceeding
#         # if not validate_update_arguments(
#         #     result=result,
#         #     citation=citation,
#         #     llm_json_output=llm_json_output,
#         #     public_url=public_url,
#         #     filename=filename,
#         #     pdf_text_content=pdf_text_content
#         # ):
#         #     return jsonify({"error": "Invalid input"}), 400

#         # # Update the DataFrame
#         # update_process_files_pd(result, citation, llm_json_output, public_url, filename, pdf_text_content)

#         # # Save the DataFrame to a local file (before calling the save to bucket method)
#         # local_file_path = os.path.join('static', 'csv', f'{SESSION_ID}.csv')  # Use session_id for the file name
#         # # Ensure the directory exists
#         # os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

#         # # Save the DataFrame locally to the file path
#         # PROCESS_FILES_PD.to_csv(local_file_path, index=False)

#     #     # Upload the CSV file to the bucket and get the public URL
#     #     processed_files_csv_url = save_csv_to_bucket_v2(local_file_path=local_file_path, bucket_name=PAPERS_PROCESSED_BUCKET, session_id=SESSION_ID)

#     except Exception as e:
#         pass
#     #     # Log the error (can be replaced with a logging solution)
#     #     print(f"Error processing file at index {current_index}: {e}")
        
#     #     # Return a generic error response
#     #     return jsonify({"error": f"An error occurred: {str(e)}"}), 500

#     # Return detailed response with the URL of the uploaded CSV
#     return jsonify({
#         'done': False,
#         'gcp_public_url': safe_value(public_url),
#         'current_index': safe_value(current_index),
#         'total_files': safe_value(len(PROCESS_FILES_PD)),
#         'extracted_text': safe_value(str(pdf_text_content)),
#         'llm_json_output': safe_value(json.dumps(llm_json_output)),
#         'result_string': safe_value(json.dumps(result)),
#         'citation': safe_value(json.dumps(citation)),
#         'papers_json_public_url': safe_value(papers_json_public_url),  # Include the URL of the saved CSV
#     }), 200

# Directory to save temporary files
TEMP_JSON_DIR = "static/temp-jsons"

@app.route('/download_papers_json')
def download_papers_json():
    # Ensure the directory exists
    if not os.path.exists(TEMP_JSON_DIR):
        os.makedirs(TEMP_JSON_DIR)
    
    # Construct the JSON URL
    json_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
    local_file_path = os.path.join(TEMP_JSON_DIR, f"{SESSION_ID}.json")
    
    # Download the JSON file
    response = requests.get(json_url)
    if response.status_code == 200:
        # Save the file locally
        with open(local_file_path, 'wb') as file:
            file.write(response.content)
        
        # Serve the file for download
        try:
            return send_file(local_file_path, as_attachment=True)
        finally:
            # Ensure the file is deleted after sending
            os.remove(local_file_path)
    else:
        return "Error: Unable to download the JSON file.", 500


@app.route('/process_files/', methods=['POST'])
def process_files():
    try:
        # Get the current index from the request body
        current_index = int(request.json.get('index', 0))
        
        # Check if the index exceeds the length of the DataFrame
        if current_index >= len(PARENT_FILES_PD):
            return jsonify({'done': True}), 200
            
        # Get the current file from the DataFrame
        current_file = PARENT_FILES_PD.iloc[current_index]
        
        # Extract necessary information from the current file
        public_url = current_file['gcp_public_url']
        filename = public_url.split('/')[-1]
        
        # Construct papers_json_public_url
        papers_json_public_url = f"https://storage.googleapis.com/{PAPERS_BUCKET_JSON_FILES}/jsons_from_pdfs/{SESSION_ID}/{SESSION_ID}.json"
        
        # Load existing PAPER_JSON_FILES
        PAPER_JSON_FILES = load_paper_json_files(papers_json_public_url)
        
        # Extract information from PDF
        result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
        pdf_text_content = extract_text_from_pdf(public_url)
        
        #llm_json_output = llm_with_JSON_output(pdf_text_content)
        llm_json_output =""
        
        # Apply safe_value to llm_json_output
        llm_json_output = safe_value(llm_json_output)
        
        # Get citation
        citation = get_default_citation()
        
        # Create new paper JSON object
        pdf_paper_json = {
            "pdf_file_url": safe_value(public_url),
            "filename": safe_value(filename),
            "result": safe_value(result),
            "pdf_text_content": safe_value(pdf_text_content),
            "llm_json_output": safe_value(llm_json_output),
            "papers_json_public_url": papers_json_public_url if papers_json_public_url else "",
            "diatoms_data": [],
            "citation": safe_value(citation)
        }
        
        # Check if paper already exists in PAPER_JSON_FILES
        if not any(paper['pdf_file_url'] == public_url for paper in PAPER_JSON_FILES):
            PAPER_JSON_FILES.append(pdf_paper_json)
            
        # Save updated PAPER_JSON_FILES
        papers_json_public_url = save_paper_json_files(papers_json_public_url, PAPER_JSON_FILES)
        

        return jsonify({
            'done': False,
            'gcp_public_url': safe_value(public_url),
            'current_index': safe_value(current_index),
            'total_files': safe_value(len(PARENT_FILES_PD)),
            'extracted_text': safe_value(str(pdf_text_content)),
            'llm_json_output': safe_value(json.dumps(llm_json_output)),
            'result_string': safe_value(json.dumps(result)),
            'citation': safe_value(json.dumps(citation)),
            'papers_json_public_url': safe_value(papers_json_public_url)
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500



# @app.route('/process_files/', methods=['POST'])
# def process_files():
#     # Get the current index from the request body
#     current_index = int(request.json.get('index', 0))
    
#     # Check if the index exceeds the length of the DataFrame
#     if current_index >= len(PARENT_FILES_PD):
#         return jsonify({'done': True}), 200
        
#     # Get the current file from the DataFrame
#     current_file = PARENT_FILES_PD.iloc[current_index]
    
#     # Extract necessary information from the current file
#     public_url = current_file['gcp_public_url']
#     filename = public_url.split('/')[-1]

#     # Get the citation (you may have to adjust this method based on how you handle citation)
#     citation = get_default_citation()

#     # Extract additional information: result, pdf text, and LLM output
#     result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
#     pdf_text_content = extract_text_from_pdf(public_url)
#     llm_json_output = llm_with_JSON_output(pdf_text_content)

#     # Validate arguments before proceeding
#     if not validate_update_arguments(
#         result=result,
#         citation=citation,
#         llm_json_output=llm_json_output,
#         public_url=public_url,
#         filename=filename,
#         pdf_text_content=pdf_text_content
#     ):
#         return jsonify({"error": "Invalid input"}), 400

#     # Update the DataFrame
#     update_process_files_pd(result, citation, llm_json_output, public_url, filename, pdf_text_content)

#     # Save the DataFrame to a local file (before calling the save to bucket method)
#     local_file_path = os.path.join('static', 'csv', f'{SESSION_ID}.csv')  # Use session_id for the file name
#     # Ensure the directory exists
#     os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

#     # Save the DataFrame locally to the file path
#     PROCESS_FILES_PD.to_csv(local_file_path, index=False)

#     # Upload the CSV file to the bucket and get the public URL
#     processed_files_csv_url = save_csv_to_bucket_v2(local_file_path=local_file_path, bucket_name=PAPERS_PROCESSED_BUCKET, session_id=SESSION_ID)

#     # Return detailed response with the URL of the uploaded CSV
#     return jsonify({
#         'done': False,
#         'gcp_public_url': safe_value(public_url),
#         'current_index': safe_value(current_index),
#         'total_files': safe_value(len(PROCESS_FILES_PD)),
#         'extracted_text': safe_value(str(pdf_text_content)),
#         'llm_json_output': safe_value(json.dumps(llm_json_output)),
#         'result_string': safe_value(json.dumps(result)),
#         'citation': safe_value(json.dumps(citation)),
#         'processed_files_csv_url': safe_value(processed_files_csv_url),  # Include the URL of the saved CSV
#     }), 200


# @app.route('/process_files/', methods=['POST'])
# def process_files():
#     current_index = int(request.json.get('index', 0))
    
#     if current_index >= len(PARENT_FILES_PD):
#         return jsonify({'done': True})
        
#     current_file = PARENT_FILES_PD.iloc[current_index]
#     public_url = current_file['gcp_public_url']
#     filename = public_url.split('/')[-1]

#     # Get citation and process PDF
#     citation = get_default_citation()
#     result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
#     pdf_text_content = extract_text_from_pdf(public_url)
#     llm_json_output = llm_with_JSON_output(pdf_text_content)

#     # Parse extracted LLM JSON output

#     figure_caption = llm_json_output.get('figure_caption', '')
#     source_material_location = llm_json_output.get('source_material_location', '')
#     source_material_coordinates =llm_json_output.get('source_material_coordinates', '')
#     source_material_description = llm_json_output.get('source_material_description', '')
#     source_material_received_from = llm_json_output.get('source_material_received_from', '')
#     source_material_date_received = llm_json_output.get('source_material_date_received', '')
#     source_material_note = llm_json_output.get('source_material_note', '')

#     # Load or initialize PROCESSED_FILES_PD
#     public_url = f"https://storage.googleapis.com/{PAPERS_PROCESSED_BUCKET}/csv/{SESSION_ID}/{SESSION_ID}.csv"
#     PROCESSED_FILES_PD = initialize_or_load_processed_files_df2(public_url) 

#     # Process each species in the parsed output
#     new_rows = []
#     for species in llm_json_output.get('diatom_species_array', []):
#         try:
#             # Extract species details
#             species_index = species.get('species_index', '')
#             species_name = species.get('species_name', '')
#             species_authors = species.get('species_authors', [])
#             species_year = species.get('species_year', '')
#             species_references = species.get('species_references', [])
#             formatted_species_name = species.get('formatted_species_name', '')
#             genus = species.get('genus', '')
#             species_magnification = species.get('species_magnification', '')
#             species_scale_bar_microns = species.get('species_scale_bar_microns', '')
#             species_note = species.get('species_note', '')

#             # Create a new row for the species
#             new_row = {
#                 'gcp_public_url': public_url,
#                 'original_filename': filename,
#                 'pdf_text_content': pdf_text_content,
#                 'file_256_hash': result.get('file_256_hash', ''),
#                 'citation_name': citation.get('name', ''),
#                 'citation_authors': ', '.join(citation.get('authors', [])),
#                 'citation_year': citation.get('year', ''),
#                 'citation_organization': citation.get('organization', ''),
#                 'citation_doi': citation.get('doi', ''),
#                 'citation_url': citation.get('url', ''),
#                 'upload_timestamp': pd.Timestamp.now(),
#                 'processed': True,
#                 'images_in_doc': result.get('images_in_doc', []),
#                 'paper_image_urls': result.get('paper_image_urls', []),
#                 'species_id': uuid.uuid4().hex,
#                 'species_index': species_index,
#                 'species_name': species_name,
#                 'species_authors': species_authors,
#                 'species_year': species_year,
#                 'species_references': species_references,
#                 'formatted_species_name': formatted_species_name,
#                 'genus': genus,
#                 'species_magnification': species_magnification,
#                 'species_scale_bar_microns': species_scale_bar_microns,
#                 'species_note': species_note,
#                 'figure_caption': figure_caption,
#                 'source_material_location': source_material_location,
#                 'source_material_coordinates': source_material_coordinates,
#                 'source_material_description': source_material_description,
#                 'source_material_received_from': source_material_received_from,
#                 'source_material_date_received': source_material_date_received,
#                 'source_material_note': source_material_note,
#                 'cropped_image_url': "",
#                 'embeddings_256': [],
#                 'embeddings_512': [],
#                 'embeddings_1024': [],
#                 'embeddings_2048': [],
#                 'embeddings_4096': [],
#                 'bbox_top_left_bottom_right': "",
#                 'yolo_bbox': "",
#                 'segmentation': ""
#             }
#             new_rows.append(new_row)
#         except Exception as e:
#             print(f"Error processing species: {species.get('species_name', 'Unknown')} - {e}")
#             continue  # Continue to next species on error

#     # Try to append new rows to PROCESSED_FILES_PD
#     try:
#         # Create DataFrame for new rows
#         new_df = pd.DataFrame(new_rows)

#         # Ensure the new DataFrame matches the schema of the existing DataFrame
#         for col in PROCESSED_FILES_PD.columns:
#             new_df[col] = new_df[col].astype(PROCESSED_FILES_PD[col].dtype)

#         # Append the new rows to the existing DataFrame
#         PROCESSED_FILES_PD = pd.concat([PROCESSED_FILES_PD, new_df], ignore_index=True)

#     except Exception as e:
#         print(f"Error appending rows to DataFrame: {e}")
#         return jsonify({'done': False, 'error': 'Failed to append rows to DataFrame'}), 500

#     # Save updated DataFrame as a temporary CSV file
#     try:
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_csv:
#             PROCESSED_FILES_PD.to_csv(temp_csv.name, index=False)
#             local_file_path = temp_csv.name  # Path to the temp CSV file

#         # Upload the temp CSV to GCP bucket
#         public_url = save_csv_to_bucket_v2(local_file_path=local_file_path, bucket_name=PAPERS_PROCESSED_BUCKET, session_id=SESSION_ID)

#     except Exception as e:
#         print(f"Error saving CSV to GCP: {e}")
#         return jsonify({'done': False, 'error': 'Failed to save CSV to GCP'}), 500

#     return jsonify({
#         'done': False,
#         'gcp_public_url': public_url,
#         'current_index': current_index,
#         'total_files': len(PARENT_FILES_PD),
#         'extracted_text': str(pdf_text_content),
#         'llm_json_output': json.dumps(llm_json_output),
#         'result_string': json.dumps(result),
#         'citation': json.dumps(citation),
#         'processed_files_csv_url': public_url,
#     })




# @app.route('/process_files/', methods=['POST'])
# def process_files():
#     current_index = int(request.json.get('index', 0))
    
#     if current_index >= len(PARENT_FILES_PD):
#         return jsonify({'done': True})
        
#     current_file = PARENT_FILES_PD.iloc[current_index]
#     public_url = current_file['gcp_public_url']
#     filename = public_url.split('/')[-1]

#     # Get citation and process PDF
#     citation = get_default_citation()
#     result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
#     pdf_text_content = extract_text_from_pdf(public_url)
#     llm_json_output = llm_with_JSON_output(pdf_text_content)

#     # Parse extracted LLM JSON output
#     parsed_output = llm_json_output
#     figure_caption = parsed_output.get('figure_caption', '')
#     source_material_location = parsed_output.get('source_material_location', '')
#     source_material_coordinates = parsed_output.get('source_material_coordinates', '')
#     source_material_description = parsed_output.get('source_material_description', '')
#     source_material_received_from = parsed_output.get('source_material_received_from', '')
#     source_material_date_received = parsed_output.get('source_material_date_received', '')
#     source_material_note = parsed_output.get('source_material_note', '')

#     # Load or initialize PROCESSED_FILES_PD
#     #PROCESSED_FILES_PD = load_or_initialize_processed_files_df(session_id=SESSION_ID, bucket_name=PAPERS_PROCESSED_BUCKET)
#     public_url = f"https://storage.googleapis.com/{PAPERS_PROCESSED_BUCKET}/csv/{SESSION_ID}/{SESSION_ID}.csv"
#     PROCESSED_FILES_PD = initialize_or_load_processed_files_df2(public_url) 

#     # Process each species in the parsed output
#     new_rows = []
#     for species in parsed_output.get('diatom_species_array', []):
#         # Extract species details
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

#         # Create a new row for the species
#         new_row = {
#             'gcp_public_url': public_url,
#             'original_filename': filename,
#             'pdf_text_content': pdf_text_content,
#             'file_256_hash': result.get('file_256_hash', ''),
#             'citation_name': citation.get('name', ''),
#             'citation_authors': ', '.join(citation.get('authors', [])),
#             'citation_year': citation.get('year', ''),
#             'citation_organization': citation.get('organization', ''),
#             'citation_doi': citation.get('doi', ''),
#             'citation_url': citation.get('url', ''),
#             'upload_timestamp': pd.Timestamp.now(),
#             'processed': True,
#             'images_in_doc': result.get('images_in_doc', []),
#             'paper_image_urls': result.get('paper_image_urls', []),
#             'species_id': uuid.uuid4().hex,
#             'species_index': species_index,
#             'species_name': species_name,
#             'species_authors': species_authors,
#             'species_year': species_year,
#             'species_references': species_references,
#             'formatted_species_name': formatted_species_name,
#             'genus': genus,
#             'species_magnification': species_magnification,
#             'species_scale_bar_microns': species_scale_bar_microns,
#             'species_note': species_note,
#             'figure_caption': figure_caption,
#             'source_material_location': source_material_location,
#             'source_material_coordinates': source_material_coordinates,
#             'source_material_description': source_material_description,
#             'source_material_received_from': source_material_received_from,
#             'source_material_date_received': source_material_date_received,
#             'source_material_note': source_material_note,
#             'cropped_image_url': "",
#             'embeddings_256': [],
#             'embeddings_512': [],
#             'embeddings_1024': [],
#             'embeddings_2048': [],
#             'embeddings_4096': [],
#             'bbox_top_left_bottom_right': "",
#             'yolo_bbox': "",
#             'segmentation': ""
#         }
#         new_rows.append(new_row)

#     # Append new rows to PROCESSED_FILES_PD
#     new_df = pd.DataFrame(new_rows)
#     for col in PROCESSED_FILES_PD.columns:
#         new_df[col] = new_df[col].astype(PROCESSED_FILES_PD[col].dtype)
#     PROCESSED_FILES_PD = pd.concat([PROCESSED_FILES_PD, new_df], ignore_index=True)

#     # Save updated PROCESSED_FILES_PD to GCS
#     processed_files_csv_url = save_df_to_gcs(PROCESSED_FILES_PD, PAPERS_PROCESSED_BUCKET, SESSION_ID)

#     time.sleep(65)  # Adjust this delay as needed for rate limiting or other requirements

#     return jsonify({
#         'done': False,
#         'gcp_public_url': public_url,
#         'current_index': current_index,
#         'total_files': len(PARENT_FILES_PD),
#         'extracted_text': str(pdf_text_content),
#         'llm_json_output': json.dumps(llm_json_output),
#         'result_string': json.dumps(result),
#         'citation': json.dumps(citation),
#         'processed_files_csv_url': processed_files_csv_url,
#     })





# @app.route('/claudeai/', methods=['POST'])
# def extract_data_with_claude():
    
#     base64_string = encode_pdf_to_base64(test_pdf_path)
    
#     claude_llm_prompt = create_claude_prompt()
    
#     claude_msg = create_messages(base64_string, claude_llm_prompt)
    
#     claude_completion = get_completion(claude_msg)
    
#     return jsonify({'claude_completion': claude_completion})
@app.route('/claudeai/', methods=['POST'])
def extract_data_with_claude():
    try:
        # Example: Encoding PDF to base64
        # base64_string = encode_pdf_to_base64(test_pdf_path)
        
        # # Create the Claude prompt
        # claude_llm_prompt = create_claude_prompt()
        
        # # Create the message for Claude
        # claude_msg = create_messages(base64_string, claude_llm_prompt)
        
        # # Get the completion from Claude
        # claude_completion = get_completion(claude_msg)  
        
        
        # claude_completion = get_llama_paper_info(test_pdf_path)
        claude_completion =""
        
        # Return the Claude completion response
        return jsonify({'claude_completion': claude_completion})

    except Exception as e:
        # Log the error and return a response
        print(f"Error occurred while extracting data with Claude: {e}")
        return jsonify({'error': 'An error occurred while fetching the completion.'}), 500


def fetch_and_process_data():
    """Fetch data from the CSV URL and properly convert synonyms to string"""
    url = "https://storage.googleapis.com/papers-diatoms-colossus/cvs/colossus.csv"
    try:
        df = pd.read_csv(url)
        # Convert the synonyms column data type to string without splitting characters
        df['synonyms'] = df['synonyms'].str.join('')
        return df.to_dict('records')
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

@app.route('/colosus')
def display_table():
    """Route to display the auto-refreshing table"""
    data = fetch_and_process_data()
    return render_template('colosus.html', data=data)


# Define the diatoms array
# azores_2_diatoms = [
#     [39, "Amphora_obtusa_var_oceanica"],
#     [40, "Amphora_obtusa"],
#     [41, "Amphora_obtusa"],
#     [42, "Amphora_obtusa"],
#     [43, "Halamphora_cymbifera"],
#     [44, "Amphora_bistriata"],
#     [45, "Amphora_praelata"],
#     [46, "Amphora_spectabilis"],
#     [47, "Amphora_ocellata"],
#     [48, "Amphora_crassa"],
#     [49, "Amphora_crassa"],
#     [50, "Amphora_crassa"],
#     [51, "Diploneis_mirabilis"],
#     [52, "Lyrella_impercepta"],
#     [53, "Amphora_cingulata"],
#     [54, "Amphora_cingulata"],
#     [55, "Amphora_cingulata"],
#     [56, "Amphora_sp_indet"],
#     [57, "Parlibellus_delognei"],
#     [58, "Parlibellus_delognei"],
#     [59, "Navicula_digitoradiata"],
#     [60, "Navicula_palpebralis"],
#     [61, "Navicula_palpebralis"],
#     [62, "Diploneis_papula"],
#     [63, "Navicula_applicita"],
#     [64, "Navicula_applicita"]
# ]


# azores_2_diatoms = [
#     {"label": ["39 Amphora_obtusa_var_oceanica"], "species": "Amphora_obtusa_var_oceanica", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["40 Amphora_obtusa"], "species": "Amphora_obtusa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["41 Amphora_obtusa"], "species": "Amphora_obtusa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["42 Amphora_obtusa"], "species": "Amphora_obtusa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["43 Halamphora_cymbifera"], "species": "Halamphora_cymbifera", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["44 Amphora_bistriata"], "species": "Amphora_bistriata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["45 Amphora_praelata"], "species": "Amphora_praelata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["46 Amphora_spectabilis"], "species": "Amphora_spectabilis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["47 Amphora_ocellata"], "species": "Amphora_ocellata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["48 Amphora_crassa"], "species": "Amphora_crassa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["49 Amphora_crassa"], "species": "Amphora_crassa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["50 Amphora_crassa"], "species": "Amphora_crassa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["51 Diploneis_mirabilis"], "species": "Diploneis_mirabilis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["52 Lyrella_impercepta"], "species": "Lyrella_impercepta", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["53 Amphora_cingulata"], "species": "Amphora_cingulata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["54 Amphora_cingulata"], "species": "Amphora_cingulata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["55 Amphora_cingulata"], "species": "Amphora_cingulata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["56 Amphora_sp_indet"], "species": "Amphora_sp_indet", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["57 Parlibellus_delognei"], "species": "Parlibellus_delognei", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["58 Parlibellus_delognei"], "species": "Parlibellus_delognei", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["59 Navicula_digitoradiata"], "species": "Navicula_digitoradiata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["60 Navicula_palpebralis"], "species": "Navicula_palpebralis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["61 Navicula_palpebralis"], "species": "Navicula_palpebralis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["62 Diploneis_papula"], "species": "Diploneis_papula", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["63 Navicula_applicita"], "species": "Navicula_applicita", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["64 Navicula_applicita"], "species": "Navicula_applicita", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''}
# ]

# azores_2_diatoms = [
#     {"label": ["39 Amphora_obtusa_var_oceanica"], "index": 39, "species": "Amphora_obtusa_var_oceanica", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["40 Amphora_obtusa"], "index": 40, "species": "Amphora_obtusa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["41 Amphora_obtusa"], "index": 41, "species": "Amphora_obtusa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["42 Amphora_obtusa"], "index": 42, "species": "Amphora_obtusa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["43 Halamphora_cymbifera"], "index": 43, "species": "Halamphora_cymbifera", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["44 Amphora_bistriata"], "index": 44, "species": "Amphora_bistriata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["45 Amphora_praelata"], "index": 45, "species": "Amphora_praelata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["46 Amphora_spectabilis"], "index": 46, "species": "Amphora_spectabilis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["47 Amphora_ocellata"], "index": 47, "species": "Amphora_ocellata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["48 Amphora_crassa"], "index": 48, "species": "Amphora_crassa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["49 Amphora_crassa"], "index": 49, "species": "Amphora_crassa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["50 Amphora_crassa"], "index": 50, "species": "Amphora_crassa", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["51 Diploneis_mirabilis"], "index": 51, "species": "Diploneis_mirabilis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["52 Lyrella_impercepta"], "index": 52, "species": "Lyrella_impercepta", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["53 Amphora_cingulata"], "index": 53, "species": "Amphora_cingulata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["54 Amphora_cingulata"], "index": 54, "species": "Amphora_cingulata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["55 Amphora_cingulata"], "index": 55, "species": "Amphora_cingulata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["56 Amphora_sp_indet"], "index": 56, "species": "Amphora_sp_indet", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["57 Parlibellus_delognei"], "index": 57, "species": "Parlibellus_delognei", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["58 Parlibellus_delognei"], "index": 58, "species": "Parlibellus_delognei", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["59 Navicula_digitoradiata"], "index": 59, "species": "Navicula_digitoradiata", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["60 Navicula_palpebralis"], "index": 60, "species": "Navicula_palpebralis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["61 Navicula_palpebralis"], "index": 61, "species": "Navicula_palpebralis", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["62 Diploneis_papula"], "index": 62, "species": "Diploneis_papula", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["63 Navicula_applicita"], "index": 63, "species": "Navicula_applicita", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''},
#     {"label": ["64 Navicula_applicita"], "index": 64, "species": "Navicula_applicita", "bbox": '', "yolo_bbox": '', "segmentation": '', "embeddings": ''}
# ]

# diatoms_data = [
#     {
#         "image_url": "/static/label-images/2_Azores.png",
#         "image_width": "",
#         "image_height": "",
#         "info": [
#             {"label": ["39 Amphora_obtusa_var_oceanica"], "index": 39, "species": "Amphora_obtusa_var_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#             {"label": ["40 Amphora_obtusa"], "index": 40, "species": "Amphora_obtusa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#             {"label": ["41 Amphora_obtusa"], "index": 41, "species": "Amphora_obtusa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#         ]
#     },
#     {
#         "image_url": "/static/label-images/5_Azores.png",
#         "image_width": "",
#         "image_height": "",
#         "info": [
#             {"label": ["108 Amphitetras_subrotundata"], "index": 108, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#             {"label": ["109 Amphitetras_subrotundata"], "index": 109, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#         ]
#     },
#     {
#         "image_url": "/static/label-images/4_Azores.png",
#         "image_width": "",
#         "image_height": "",
#         "info": [
#             {"label": ["88 Actinocyclus_sp_indet"], "index": 88, "species": "Actinocyclus_sp_indet", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#             {"label": ["89 Endictya_oceanica"], "index": 89, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
#         ]
#     }
# ]



# @app.route('/label', methods=['GET', 'POST'])
# def label():
#     global azores_2_diatoms
    
#     if request.method == 'POST':
#         # Get updated diatom data
#         updated_diatom = request.json
        
#         # Update the specific diatom in the array
#         for i, diatom in enumerate(azores_2_diatoms):
#             if diatom['label'][0] == updated_diatom['label'][0]:
#                 azores_2_diatoms[i]['bbox'] = updated_diatom['bbox']
#                 break
                
#         return jsonify({'success': True})
        
#     # GET request returns the template
#     return render_template('label-react.html', diatoms=azores_2_diatoms)

# # Add a route to get the current state of the diatoms array
# @app.route('/api/diatoms', methods=['GET'])
# def get_diatoms():
#     return jsonify(azores_2_diatoms)

# @app.route('/label')
# def label():
#     return render_template('label.html', diatoms=azores_2_diatoms)
diatoms_data = [
    {
        "image_url": "/static/label-images/2_Azores.png",
        "image_width": "",
        "image_height": "",
        "info": [
            {"label": ["39 Amphora_obtusa_var_oceanica"], "index": 39, "species": "Amphora_obtusa_var_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["40 Amphora_obtusa"], "index": 40, "species": "Amphora_obtusa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["41 Amphora_obtusa"], "index": 41, "species": "Amphora_obtusa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["42 Amphora_obtusa"], "index": 42, "species": "Amphora_obtusa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["43 Halamphora_cymbifera"], "index": 43, "species": "Halamphora_cymbifera", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["44 Amphora_bistriata"], "index": 44, "species": "Amphora_bistriata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["45 Amphora_praelata"], "index": 45, "species": "Amphora_praelata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["46 Amphora_spectabilis"], "index": 46, "species": "Amphora_spectabilis", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["47 Amphora_ocellata"], "index": 47, "species": "Amphora_ocellata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["48 Amphora_crassa"], "index": 48, "species": "Amphora_crassa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["49 Amphora_crassa"], "index": 49, "species": "Amphora_crassa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["50 Amphora_crassa"], "index": 50, "species": "Amphora_crassa", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["51 Diploneis_mirabilis"], "index": 51, "species": "Diploneis_mirabilis", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["52 Lyrella_impercepta"], "index": 52, "species": "Lyrella_impercepta", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["53 Amphora_cingulata"], "index": 53, "species": "Amphora_cingulata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["54 Amphora_cingulata"], "index": 54, "species": "Amphora_cingulata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["55 Amphora_cingulata"], "index": 55, "species": "Amphora_cingulata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["56 Amphora_sp_indet"], "index": 56, "species": "Amphora_sp_indet", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["57 Parlibellus_delognei"], "index": 57, "species": "Parlibellus_delognei", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["58 Parlibellus_delognei"], "index": 58, "species": "Parlibellus_delognei", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["59 Navicula_digitoradiata"], "index": 59, "species": "Navicula_digitoradiata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["60 Navicula_palpebralis"], "index": 60, "species": "Navicula_palpebralis", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["61 Navicula_palpebralis"], "index": 61, "species": "Navicula_palpebralis", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["62 Diploneis_papula"], "index": 62, "species": "Diploneis_papula", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["63 Navicula_applicita"], "index": 63, "species": "Navicula_applicita", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["64 Navicula_applicita"], "index": 64, "species": "Navicula_applicita", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""}
        ]
    },
    {
        "image_url": "/static/label-images/5_Azores.png",
        "image_width": "",
        "image_height": "",
        "info": [
            {"label": ["108 Amphitetras_subrotundata"], "index": 108, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["109 Amphitetras_subrotundata"], "index": 109, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["110 Amphitetras_subrotundata"], "index": 110, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["111 Amphitetras_subrotundata"], "index": 111, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["112 Amphitetras_subrotundata"], "index": 112, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["113 Stictodiscus_parallelus_fo_hexagona"], "index": 113, "species": "Stictodiscus_parallelus_fo_hexagona", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["114 Stictodiscus_parallelus_fo_hexagona"], "index": 114, "species": "Stictodiscus_parallelus_fo_hexagona", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["115 Stictodiscus_parallelus_fo_hexagona"], "index": 115, "species": "Stictodiscus_parallelus_fo_hexagona", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["116 Triceratium_pentacrinus_fo_quadrata"], "index": 116, "species": "Triceratium_pentacrinus_fo_quadrata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["117 Triceratium_pentacrinus_fo_quadrata"], "index": 117, "species": "Triceratium_pentacrinus_fo_quadrata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["118 Biddulphia_biddulphiana"], "index": 118, "species": "Biddulphia_biddulphiana", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["119 Triceratium_finnmarchicum"], "index": 119, "species": "Triceratium_finnmarchicum", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""}
        ]
    },
    {
        "image_url": "/static/label-images/4_Azores.png",
        "image_width": "",
        "image_height": "",
        "info": [
            {"label": ["88 Actinocyclus_sp_indet"], "index": 88, "species": "Actinocyclus_sp_indet", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["89 Endictya_oceanica"], "index": 89, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["90 Endictya_oceanica"], "index": 90, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["91 Endictya_oceanica"], "index": 91, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["92 Endictya_oceanica"], "index": 92, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["93 Endictya_oceanica"], "index": 93, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["94 Endictya_oceanica"], "index": 94, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["95 Endictya_oceanica"], "index": 95, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["96 Endictya_oceanica"], "index": 96, "species": "Endictya_oceanica", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["97 Biddulphia_biddulphiana"], "index": 97, "species": "Biddulphia_biddulphiana", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["98 Amphitetras_subrotundata"], "index": 98, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["99 Amphitetras_subrotundata"], "index": 99, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["100 Amphitetras_subrotundata"], "index": 100, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""},
            {"label": ["101 Amphitetras_subrotundata"], "index": 101, "species": "Amphitetras_subrotundata", "bbox": "", "yolo_bbox": "", "segmentation": "", "embeddings": ""}
        ]
    }
]


# def load_saved_labels():
#     """Load saved labels for current session if they exist"""
#     save_path = os.path.join('static', 'labels', f'{SESSION_ID}.json')
#     if os.path.exists(save_path):
#         with open(save_path, 'r') as f:
#             return json.load(f)
#     return diatoms_data  # Return base data if no saved labels exist

# def save_labels(data):
#     """Save labels for current session"""
#     os.makedirs(os.path.join('static', 'labels'), exist_ok=True)
#     save_path = os.path.join('static', 'labels', f'{SESSION_ID}.json')
#     with open(save_path, 'w') as f:
#         json.dump(data, f, indent=4)

# @app.route('/label', methods=['GET', 'POST'])
# def label():
#     if request.method == 'POST':
#         updated_data = request.json
#         save_labels(updated_data)
#         return jsonify({'success': True})
    
#     return render_template('label-react.html')

# @app.route('/api/diatoms', methods=['GET'])
# def get_diatoms():
#     image_index = request.args.get('index', 0, type=int)
    
#     # Load current session's data
#     current_data = load_saved_labels()
    
#     # Ensure index is within bounds
#     image_index = min(max(0, image_index), len(current_data) - 1)
    
#     return jsonify({
#         'current_index': image_index,
#         'total_images': len(current_data),
#         'data': current_data[image_index]
#     })

# @app.route('/api/save', methods=['POST'])
# def save():
#     try:
#         current_data = load_saved_labels()
#         image_index = request.json.get('image_index', 0)
#         updated_info = request.json.get('info', [])
        
#         # Update only the info for the current image
#         current_data[image_index]['info'] = updated_info
        
#         # Save the entire updated dataset
#         save_labels(current_data)
        
#         return jsonify({
#             'success': True,
#             'message': 'Labels saved successfully',
#             'timestamp': datetime.now().isoformat(),
#             'saved_index': image_index
#         })
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500



# @app.route('/api/download', methods=['GET'])
# def download_labels():
#     """Download the saved labels file for current session"""
#     try:
#         save_path = os.path.join('static', 'labels', f'{SESSION_ID}.json')
        
#         # Check if file exists
#         if not os.path.exists(save_path):
#             return jsonify({'error': 'No saved labels found'}), 404
            
#         # Return the file as an attachment
#         return send_file(
#             save_path,
#             mimetype='application/json',
#             as_attachment=True,
#             download_name=f'diatom_labels_{SESSION_ID}.json'
#         )
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500


def get_gcp_json_url():
    """Generate the public URL for the JSON file in GCP Storage"""
    return f"https://storage.googleapis.com/{PAPERS_BUCKET_LABELLING}/labels/{SESSION_ID}/{SESSION_ID}.json"

def load_saved_labels():
    """Load saved labels for current session if they exist"""
    # First try to load from GCP
    try:
        json_public_url = get_gcp_json_url()
        response = requests.get(json_public_url)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error loading from GCP: {e}")

    # Fallback to local file if GCP fails
    save_path = os.path.join('static', 'labels', f'{SESSION_ID}.json')
    if os.path.exists(save_path):
        with open(save_path, 'r') as f:
            return json.load(f)
    
    return diatoms_data  # Return base data if no saved labels exist

def save_labels(data):
    """Save labels for current session to both local and GCP storage"""
    # Ensure local directory exists
    os.makedirs(os.path.join('static', 'labels'), exist_ok=True)
    
    # Save locally
    local_save_path = os.path.join('static', 'labels', f'{SESSION_ID}.json')
    with open(local_save_path, 'w') as f:
        json.dump(data, f, indent=4)
    
    # Save to GCP
    try:
        save_json_to_bucket(local_save_path, PAPERS_BUCKET_LABELLING, SESSION_ID)
    except Exception as e:
        print(f"Error saving to GCP: {e}")
        # Continue execution even if GCP save fails

@app.route('/label', methods=['GET', 'POST'])
def label():
    if request.method == 'POST':
        updated_data = request.json
        save_labels(updated_data)
        return jsonify({'success': True})
    
    return render_template('label-react.html')

@app.route('/api/diatoms', methods=['GET'])
def get_diatoms():
    image_index = request.args.get('index', 0, type=int)
    
    # Load current session's data
    current_data = load_saved_labels()
    
    # Ensure index is within bounds
    image_index = min(max(0, image_index), len(current_data) - 1)
    
    return jsonify({
        'current_index': image_index,
        'total_images': len(current_data),
        'data': current_data[image_index]
    })

@app.route('/api/save', methods=['POST'])
def save():
    try:
        current_data = load_saved_labels()
        image_index = request.json.get('image_index', 0)
        updated_info = request.json.get('info', [])
        
        # Update only the info for the current image
        current_data[image_index]['info'] = updated_info
        
        # Save the entire updated dataset
        save_labels(current_data)
        
        return jsonify({
            'success': True,
            'message': 'Labels saved successfully',
            'timestamp': datetime.now().isoformat(),
            'saved_index': image_index,
            'gcp_url': get_gcp_json_url()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/download', methods=['GET'])
def download_labels():
    """Download the saved labels file for current session"""
    try:
        # First try to download from GCP
        try:
            json_public_url = get_gcp_json_url()
            response = requests.get(json_public_url)
            if response.status_code == 200:
                # Save the GCP data temporarily and send it
                temp_path = os.path.join('static', 'labels', f'temp_{SESSION_ID}.json')
                with open(temp_path, 'w') as f:
                    json.dump(response.json(), f, indent=4)
                
                return send_file(
                    temp_path,
                    mimetype='application/json',
                    as_attachment=True,
                    download_name=f'diatom_labels_{SESSION_ID}.json'
                )
        except Exception as e:
            print(f"Error downloading from GCP: {e}")

        # Fallback to local file if GCP fails
        local_save_path = os.path.join('static', 'labels', f'{SESSION_ID}.json')
        
        # Check if file exists
        if not os.path.exists(local_save_path):
            return jsonify({'error': 'No saved labels found'}), 404
        
        # Return the file as an attachment
        return send_file(
            local_save_path,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'diatom_labels_{SESSION_ID}.json'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500






if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))