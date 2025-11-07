# Legal Document Splitter API

FastAPI-based service for splitting Russian legal documents (DOCX/PDF) into individual articles with NLP metadata extraction.

## 🎨 Web Interface

**NEW**: Modern web interface available! No coding required.

After starting the server, open your browser:
```
http://localhost:8000
```

Features:
- 📤 Drag & drop file upload
- 🔄 Real-time progress tracking
- ⚙️ Merge mode toggle
- 📥 One-click download

See [UI_GUIDE.md](UI_GUIDE.md) for detailed interface documentation.

## Features

- **Multi-format support**: Process both DOCX and PDF files
- **Batch processing**: Upload multiple files at once
- **Merge mode**: Option to merge all files into single output or keep separate
- **Async processing**: Non-blocking job-based architecture
- **NLP metadata**: Automatic keyword and topic extraction using SpaCy
- **Hierarchical structure**: Preserves document structure (Раздел/Глава/Статья)
- **Auto-cleanup**: Temporary files cleaned after download or timeout

## Architecture

```
POST /upload → job_id → Background Processing → GET /status/{job_id} → GET /download/{job_id}
```

## Installation & Deployment

### Using Docker (Recommended)

```bash
# Build and run
docker-compose up -d

# Or build manually
docker build -t legal-doc-splitter .
docker run -p 8000:8000 legal-doc-splitter
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Download SpaCy model
python -m spacy download ru_core_news_sm

# Run server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Usage

### Web Interface (Recommended for most users)

1. Start the server:
```bash
docker-compose up -d
```

2. Open browser:
```
http://localhost:8000
```

3. Upload files, configure options, and download results!

See [UI_GUIDE.md](UI_GUIDE.md) for complete interface guide.

### Programmatic API

### 1. Upload Documents

```bash
# Single file, separate output
curl -X POST "http://localhost:8000/upload" \
  -F "files=@document.docx" \
  -F "merge_mode=false"

# Multiple files, merged output
curl -X POST "http://localhost:8000/upload" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.docx" \
  -F "merge_mode=true"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Files uploaded successfully. Processing started.",
  "files_received": 2
}
```

### 2. Check Job Status

```bash
curl "http://localhost:8000/status/{job_id}"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "message": "Processing file 2/3: document.pdf",
  "total_articles": null,
  "error": null
}
```

**Status values:**
- `pending`: Job queued
- `processing`: Currently processing
- `completed`: Ready for download
- `failed`: Processing failed

### 3. Download Results

```bash
curl "http://localhost:8000/download/{job_id}" -o results.zip
```

Returns a ZIP archive with markdown files. Files are auto-deleted after download.

### 4. Health Check

```bash
curl "http://localhost:8000/health"
```

## Python Client Example

```python
import requests
import time
from pathlib import Path

API_URL = "http://localhost:8000"

def process_documents(files: list[Path], merge_mode: bool = False):
    # Upload files
    files_data = [
        ('files', (f.name, open(f, 'rb'), 'application/octet-stream'))
        for f in files
    ]
    
    response = requests.post(
        f"{API_URL}/upload",
        files=files_data,
        data={'merge_mode': merge_mode}
    )
    
    job_id = response.json()['job_id']
    print(f"Job created: {job_id}")
    
    # Poll for completion
    while True:
        status_response = requests.get(f"{API_URL}/status/{job_id}")
        status_data = status_response.json()
        
        print(f"Status: {status_data['status']} - {status_data['progress']}% - {status_data['message']}")
        
        if status_data['status'] == 'completed':
            break
        elif status_data['status'] == 'failed':
            raise Exception(f"Processing failed: {status_data['error']}")
        
        time.sleep(2)
    
    # Download results
    download_response = requests.get(f"{API_URL}/download/{job_id}")
    output_file = f"results_{job_id}.zip"
    
    with open(output_file, 'wb') as f:
        f.write(download_response.content)
    
    print(f"Downloaded: {output_file}")
    return output_file

# Usage
files = [
    Path("document1.docx"),
    Path("document2.pdf")
]
result = process_documents(files, merge_mode=False)
```

## Output Format

Each article is saved as a markdown file with:

```markdown
# Статья 720.

## Раздел 4.

### Глава 36.

[Article content...]

## Keywords
заём, заёмщик, предмет, целевой, договор

## Topic
заём
```

**Filename structure:**
```
{document_name}_{section}_{chapter}_{article}_{description}_{keywords}.md
```

Example:
```
Гражданский_кодекс_Раздел_4_Глава_36_Статья_720_Целевой_заем_заём_заёмщик.md
```

## Configuration

Environment variables:
- `CLEANUP_TIMEOUT`: Job cleanup timeout (default: 1 hour)
- `TEMP_DIR`: Temporary files directory (default: `/tmp/jobs`)

## Dependencies

- FastAPI: Web framework
- SpaCy: NLP processing (ru_core_news_sm model)
- pdfplumber: PDF text extraction
- python-docx: DOCX text extraction
- LangChain: Document schema

## Limitations

- In-memory job state (lost on restart - use Redis for production)
- No authentication (add OAuth2/API keys for production)
- File size limits depend on server resources
- SpaCy model downloaded on container start (slower first boot)

## Production Considerations

For production deployment:
1. Add persistent job storage (Redis/PostgreSQL)
2. Implement authentication/authorization
3. Add rate limiting
4. Use persistent volume for `/tmp/jobs`
5. Configure nginx reverse proxy
6. Enable HTTPS
7. Add monitoring (Prometheus/Grafana)
8. Consider pre-building Docker image with SpaCy model

## License

Open source - adapt as needed.