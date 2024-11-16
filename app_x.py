# app.py
import os
from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
from google.cloud import storage
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = b'\xcc^\x91\xea\x17-\xd0W\x03\xa7\xf8J0\xac8\xc5'
app.config['SECURITY_PASSWORD_SALT'] = 'thisistheSALTforcreatingtheCONFIRMATIONtoken'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Configure constants
BUCKET_NAME = 'papers-bucket-mmm'
SESSION_ID = 'eb9db0ca54e94dbc82cffdab497cde13'
SAMPLE_ID = '8c583173bc904ce596d5de69ac432acb'
ALLOWED_EXTENSIONS = {'pdf'}

UPLOAD_DIR = os.path.join(os.getcwd(), 'temp_uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_to_bucket(local_file_path, filename):
    try:
        secret_json = os.getenv('GOOGLE_SECRET_JSON')
        client = storage.Client.from_service_account_info(json.loads(secret_json))
        bucket = client.bucket(BUCKET_NAME)
        
        # Create the full path in the bucket
        blob_name = f"{SESSION_ID}/{SAMPLE_ID}/papers/pdf/{filename}"
        blob = bucket.blob(blob_name)
        
        # Upload the file
        blob.upload_from_filename(local_file_path)
        
        # Generate the public URL
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
        return public_url
    except Exception as e:
        print(f"Error uploading file: {e}")
        return None

def get_uploaded_files():
    try:
        secret_json = os.getenv('GOOGLE_SECRET_JSON')
        client = storage.Client.from_service_account_info(json.loads(secret_json))
        bucket = client.bucket(BUCKET_NAME)
        
        # List all blobs in the PDF directory
        prefix = f"{SESSION_ID}/{SAMPLE_ID}/papers/pdf/"
        blobs = bucket.list_blobs(prefix=prefix)
        
        # Get file information
        files = []
        for blob in blobs:
            file_info = {
                'name': blob.name.split('/')[-1],
                'url': f"https://storage.googleapis.com/{BUCKET_NAME}/{blob.name}",
                'size': f"{blob.size / 1024 / 1024:.2f} MB",
                'updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S')
            }
            files.append(file_info)
        
        return files
    except Exception as e:
        print(f"Error listing files: {e}")
        return []

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if any file was uploaded
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        
        # If no file selected
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        # If file is valid and allowed
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Create temp directory if it doesn't exist
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save file temporarily
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(temp_path)
            
            # Upload to Google Cloud Storage
            public_url = save_file_to_bucket(temp_path, filename)
            
            # Remove temporary file
            os.remove(temp_path)
            
            if public_url:
                flash('File uploaded successfully')
            else:
                flash('Error uploading file')
            
            return redirect(url_for('upload_file'))
        else:
            flash('Invalid file type. Only PDF files are allowed.')
            return redirect(request.url)

    # Get list of uploaded files
    files = get_uploaded_files()
    return render_template('upload_images.html', files=files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))