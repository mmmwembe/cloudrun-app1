FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for PyMuPDF
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the application files
COPY . .

# Create necessary directories
RUN mkdir -p templates temp_uploads

# Make sure the application has permission to write to temp_uploads
RUN chmod 777 temp_uploads

# The command to run the application
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app