import os
from flask import Flask, render_template, request, send_file, jsonify, session, redirect, url_for , flash, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = b'\xcc^\x91\xea\x17-\xd0W\x03\xa7\xf8J0\xac8\xc5'
app.config['SECURITY_PASSWORD_SALT']='thisistheSALTforcreatingtheCONFIRMATIONtoken'

bucket_name ='papers-bucket-mmm'
session_id = 'eb9db0ca54e94dbc82cffdab497cde13'
sample_id = '8c583173bc904ce596d5de69ac432acb'


@app.route('/')
def home():
    #long_string = os.getenv('LONG_STRING', 'Environment variable not set')
    #return f'<h1>LONG_STRING value:</h1><p>{long_string}</p>'
    return render_template('upload_images.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))