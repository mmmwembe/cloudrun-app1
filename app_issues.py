# app.py
import os
import hashlib
from flask import Flask, render_template, request, flash, redirect, url_for, Response, jsonify
from werkzeug.utils import secure_filename
from google.cloud import storage
import json
from dotenv import load_dotenv
import pandas as pd
import fitz  # PyMuPDF

load_dotenv()

app = Flask(__name__)
app.secret_key = b'\xcc^\x91\xea\x17-\xd0W\x03\xa7\xf8J0\xac8\xc5'
app.config['SECURITY_PASSWORD_SALT'] = 'thisistheSALTforcreatingtheCONFIRMATIONtoken'
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Configure bucket names
BUCKET_ORIGINAL_PAPERS = 'papers-parent-bucket-mmm'
BUCKET_SPLIT_PAGES = 'papers-split-pages-bucket-mmm'
BUCKET_EXTRACTED_IMAGES = 'papers-extracted-images-bucket-mmm'
BUCKET_PAPER_TRACKER_CSV = 'papers-extracted-pages-csv-bucket-mmm'

ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_DIR = os.path.join(os.getcwd(), 'temp_uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_storage_client():
    secret_json = os.getenv('GOOGLE_SECRET_JSON')
    return storage.Client.from_service_account_info(json.loads(secret_json))

def generate_hash(filename):
    return hashlib.md5(filename.encode()).hexdigest()

def get_default_citation():
    return {
        'name': "Stuart R. Stidolph Diatom Atlas",
        'authors': ["S.R. Stidolph", "F.A.S. Sterrenburg", "K.E.L. Smith", "A. Kraberg"],
        'year': "2012",
        'organization': "U.S. Geological Survey",
        'doi': "2012-1163",
        'url': "http://pubs.usgs.gov/of/2012/1163/"
    }

def upload_file_to_bucket(local_file_path, filename, bucket_name):
    try:
        client = get_storage_client()
        bucket = client.bucket(bucket_name)
        file_hash = generate_hash(filename)
        
        blob_name = f"papers/{file_hash}/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_file_path)
        
        return {
            'file_path_public_url': blob.public_url,
            'full_citation': get_default_citation(),
            'hash': file_hash
        }
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

def extract_and_save_pages(pdf_info):
    try:
        client = get_storage_client()
        results = []
        
        # Download the PDF
        pdf_path = os.path.join(UPLOAD_DIR, f"temp_{pdf_info['hash']}.pdf")
        storage.Blob(
            pdf_info['file_path_public_url'].split('/')[-1],
            client.bucket(BUCKET_ORIGINAL_PAPERS)
        ).download_to_filename(pdf_path)
        
        # Process PDF pages
        pdf_document = fitz.open(pdf_path)
        for page_idx in range(len(pdf_document)):
            page = pdf_document[page_idx]
            
            # Save extracted page
            page_filename = f"{pdf_info['hash']}_page_{page_idx+1}.pdf"
            page_path = os.path.join(UPLOAD_DIR, page_filename)
            
            sub_pdf = fitz.open()
            sub_pdf.insert_pdf(pdf_document, from_page=page_idx, to_page=page_idx)
            sub_pdf.save(page_path)
            
            # Upload extracted page
            split_bucket = client.bucket(BUCKET_SPLIT_PAGES)
            page_blob_name = f"extracted_pdfs/{pdf_info['hash']}/{page_filename}"
            page_blob = split_bucket.blob(page_blob_name)
            page_blob.upload_from_filename(page_path)
            
            # Check for images
            image_url = None
            contains_figure = False
            if len(page.get_images()) > 0:
                contains_figure = True
                # Save the first image found
                img = page.get_images()[0]
                pix = pdf_document.extract_image(img[0])
                img_path = os.path.join(UPLOAD_DIR, f"{page_filename}_image.jpg")
                with open(img_path, 'wb') as img_file:
                    img_file.write(pix["image"])
                
                # Upload image
                img_bucket = client.bucket(BUCKET_EXTRACTED_IMAGES)
                img_blob_name = f"{pdf_info['hash']}/{page_filename}_image.jpg"
                img_blob = img_bucket.blob(img_blob_name)
                img_blob.upload_from_filename(img_path)
                image_url = img_blob.public_url
                
                os.remove(img_path)
            
            results.append({
                'file_path_public_url': page_blob.public_url,
                'page_index': page_idx,
                'page_number': page_idx + 1,  # Assuming sequential numbering
                'contains_figure': contains_figure,
                'figure_name': f"Figure {page_idx + 1}" if contains_figure else "",
                'image_public_url': image_url,
                'child_pdf_public_url': page_blob.public_url
            })
            
            os.remove(page_path)
        
        pdf_document.close()
        os.remove(pdf_path)
        
        return results
    except Exception as e:
        print(f"Error extracting pages: {e}")
        return None

def save_to_tracker_csv(extracted_pages_info):
    try:
        df = pd.DataFrame(extracted_pages_info)
        
        # Save to CSV in the designated bucket
        client = get_storage_client()
        bucket = client.bucket(BUCKET_PAPER_TRACKER_CSV)
        
        csv_blob = bucket.blob('papers-tracker.csv')
        csv_blob.upload_from_string(df.to_csv(index=False))
        
        return True
    except Exception as e:
        print(f"Error saving tracker CSV: {e}")
        return False

@app.route('/process_pdf', methods=['POST'])
def process_pdf():
    try:
        file_info = request.get_json()
        extracted_pages = extract_and_save_pages(file_info)
        if extracted_pages:
            save_to_tracker_csv(extracted_pages)
            return jsonify({'status': 'success', 'pages': extracted_pages})
        return jsonify({'status': 'error', 'message': 'Failed to process PDF'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'files[]' not in request.files:
            flash('No files selected')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        if not files or all(file.filename == '' for file in files):
            flash('No files selected')
            return redirect(request.url)
        
        uploaded_files = []
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                try:
                    file.save(temp_path)
                    upload_result = upload_file_to_bucket(temp_path, filename, BUCKET_ORIGINAL_PAPERS)
                    
                    if upload_result:
                        uploaded_files.append(upload_result)
                    
                    os.remove(temp_path)
                except Exception as e:
                    print(f"Error processing file {filename}: {e}")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        
        return jsonify({'status': 'success', 'files': uploaded_files})

    return render_template('upload_images.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))