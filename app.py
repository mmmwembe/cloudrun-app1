# app.py
import os
from flask import Flask, render_template, request, flash, redirect, url_for, Response, jsonify
from werkzeug.utils import secure_filename
from google.cloud import storage
import json
from dotenv import load_dotenv
import pandas as pd
from modules.process_pdfs import process_pdf
from modules.claude_ai import create_claude_prompt, encode_pdf_to_base64, create_messages, get_completion
from modules.groq_llama import get_llama_paper_info
from modules.gcp_ops import save_file_to_bucket, save_tracker_csv, initialize_paper_upload_tracker_df_from_gcp
# save_file_to_bucket(artifact_url, session_id, file_hash_num, bucket_name, subdir="papers"
from datetime import datetime
from modules.llm_ops import llm_parsed_output_from_text, create_messages, llm_with_JSON_output
from modules.pdf_image_and_metadata_handler import extract_images_and_metadata_from_pdf
from modules.pandas_and_gcp import save_df_to_gcs, load_or_initialize_processed_files_df, update_processed_files_df_tracking
import requests
# from langchain_community.document_loaders import PyPDFLoader
import tempfile
from modules.utils import extract_text_from_pdf
import time

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
global PROCESSED_FILES_PD
PROCESSED_FILES_PD = load_or_initialize_processed_files_df(session_id=SESSION_ID,bucket_name=PAPERS_PROCESSED_BUCKET)



# global CHILD_FILES_PD
# CHILD_FILES_PD = pd.DataFrame(columns = [
#     # Child-specific fields
#     'child_pdf_file_url',
#     'has_images',
#     'num_of_images',
#     'page_number',
#     'image_urls_array',
    
#     # Parent fields from PARENT_FILES_PD
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
    
    return render_template('process_file.html', number_of_files=num_rows)

@app.route('/process_files/', methods=['POST'])
def process_files():
    
    current_index = int(request.json.get('index', 0))
    
    if current_index >= len(PARENT_FILES_PD):
        return jsonify({'done': True})
        
    current_file = PARENT_FILES_PD.iloc[current_index]
    
    public_url = current_file['gcp_public_url']
    
        # Extract filename from the public_url
    filename = public_url.split('/')[-1]

    # Get Info
    citation = get_default_citation()
    result = extract_images_and_metadata_from_pdf(public_url, SESSION_ID, BUCKET_EXTRACTED_IMAGES)
    pdf_text_content= extract_text_from_pdf(public_url)
    llm_json_output = llm_with_JSON_output(pdf_text_content)
    
    
    citation_string = json.dumps(citation, indent=4) 
    result_string = json.dumps(result, indent=4)
    extracted_text_str = str(pdf_text_content)
    llm_json_output_string = json.dumps(llm_json_output) 
    
    PROCESSED_FILES_PD = load_or_initialize_processed_files_df(session_id=SESSION_ID,bucket_name=PAPERS_PROCESSED_BUCKET)
    
    # This updates PROCESSED_FILES_PD
    # filename, citation, result, pdf_text_content, llm_json_output, PROCESSED_FILES_PD = update_processed_files_df_tracking(public_url, citation, SESSION_ID, BUCKET_EXTRACTED_IMAGES,PROCESSED_FILES_PD)

    
    # Save PD
    processed_files_csv_url = f"https://storage.googleapis.com/{PAPERS_PROCESSED_BUCKET}/csv/{SESSION_ID}/{SESSION_ID}.csv"
    # processed_files_csv_url = save_df_to_gcs(PROCESSED_FILES_PD, PAPERS_PROCESSED_BUCKET, SESSION_ID) 
    
    time.sleep(65)
    
    
    # TO-DO: UPDATE PARENT_FILES_PD 
    

    return jsonify({
        'done': False,
        'gcp_public_url': current_file['gcp_public_url'],
        'current_index': current_index,
        'total_files': len(PARENT_FILES_PD),
        'extracted_text': extracted_text_str,
        'llm_json_output': llm_json_output_string,
        'result_string': result_string,
        'citation': citation_string,
        'processed_files_csv_url': processed_files_csv_url,
    })


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
        
        
        claude_completion = get_llama_paper_info(test_pdf_path)
        
        # Return the Claude completion response
        return jsonify({'claude_completion': claude_completion})

    except Exception as e:
        # Log the error and return a response
        print(f"Error occurred while extracting data with Claude: {e}")
        return jsonify({'error': 'An error occurred while fetching the completion.'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))