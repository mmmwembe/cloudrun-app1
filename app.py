import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    long_string = os.getenv('LONG_STRING', 'Environment variable not set')
    return f'<h1>LONG_STRING value:</h1><p>{long_string}</p>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))