FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app main:app