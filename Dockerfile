FROM python:3.11-slim

WORKDIR /app

# System dependencies required by OpenCV, Tesseract and pyzbar/ZBar
RUN apt-get update && apt-get install -y \
    libzbar0 \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}