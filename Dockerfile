FROM python:3.11-slim
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/
COPY /ingest_bundle /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app /app/app
