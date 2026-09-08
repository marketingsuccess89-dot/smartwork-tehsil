# Official lightweight Python 3.11 image for Hugging Face Spaces
FROM python:3.11-slim

# Install system dependencies & Hindi / Devanagari fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-indic \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for Docker cache optimization
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Hugging Face Spaces runs on port 7860
EXPOSE 7860

# Run FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
