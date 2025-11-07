FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY processor.py .
COPY extractors.py .
COPY models.py .
COPY static/ ./static/

# Create temp directory
RUN mkdir -p /tmp/jobs

# Expose port
EXPOSE 8000

# Download SpaCy model on container start and run the application
CMD python -m spacy download ru_core_news_sm && \
    uvicorn main:app --host 0.0.0.0 --port 8000
