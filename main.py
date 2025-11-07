import os
import uuid
import shutil
import zipfile
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import spacy

from models import UploadResponse, JobStatusResponse, JobStatus
from processor import DocumentProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
jobs: Dict[str, Dict] = {}
nlp_model: Optional[spacy.language.Language] = None
processor: Optional[DocumentProcessor] = None

# Configuration
TEMP_DIR = Path("/tmp/jobs")
TEMP_DIR.mkdir(exist_ok=True)
CLEANUP_TIMEOUT = timedelta(hours=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load SpaCy model on startup, cleanup on shutdown."""
    global nlp_model, processor
    
    logger.info("Starting up: Loading SpaCy model...")
    try:
        nlp_model = spacy.load('ru_core_news_sm')
        processor = DocumentProcessor(nlp_model)
        logger.info("SpaCy model loaded successfully.")
    except OSError:
        logger.error("SpaCy model not found. Downloading...")
        os.system("python -m spacy download ru_core_news_sm")
        nlp_model = spacy.load('ru_core_news_sm')
        processor = DocumentProcessor(nlp_model)
        logger.info("SpaCy model downloaded and loaded.")
    
    yield
    
    logger.info("Shutting down: Cleaning up temporary files...")
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)


app = FastAPI(
    title="Legal Document Splitter API",
    description="Split legal documents (DOCX/PDF) into articles with NLP metadata",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


def cleanup_old_jobs():
    """Remove old job directories."""
    cutoff_time = datetime.now() - CLEANUP_TIMEOUT
    for job_id, job_data in list(jobs.items()):
        job_time = job_data.get('created_at', datetime.now())
        if job_time < cutoff_time:
            logger.info(f"Cleaning up old job: {job_id}")
            job_dir = TEMP_DIR / job_id
            if job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)
            del jobs[job_id]


def create_zip_archive(source_dir: Path, output_zip: Path) -> Path:
    """Create a zip archive from directory contents."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)
    return output_zip


async def process_documents_job(
    job_id: str,
    file_paths: List[Path],
    merge_mode: bool
):
    """Background task to process documents."""
    try:
        jobs[job_id]['status'] = JobStatus.PROCESSING
        jobs[job_id]['message'] = "Processing documents..."
        
        job_dir = TEMP_DIR / job_id
        output_base_dir = job_dir / "output"
        output_base_dir.mkdir(exist_ok=True)
        
        total_articles = 0
        
        if merge_mode:
            # Process all files into a single output directory
            merged_output_dir = output_base_dir / "merged_articles"
            merged_output_dir.mkdir(exist_ok=True)
            
            for idx, file_path in enumerate(file_paths):
                jobs[job_id]['message'] = f"Processing file {idx+1}/{len(file_paths)}: {file_path.name}"
                jobs[job_id]['progress'] = int((idx / len(file_paths)) * 90)
                
                result = processor.process_document(
                    str(file_path),
                    str(merged_output_dir)
                )
                total_articles += result['articles_count']
                logger.info(f"Processed {file_path.name}: {result['articles_count']} articles")
        else:
            # Process each file into separate directories
            for idx, file_path in enumerate(file_paths):
                jobs[job_id]['message'] = f"Processing file {idx+1}/{len(file_paths)}: {file_path.name}"
                jobs[job_id]['progress'] = int((idx / len(file_paths)) * 90)
                
                doc_name = file_path.stem
                file_output_dir = output_base_dir / doc_name
                file_output_dir.mkdir(exist_ok=True)
                
                result = processor.process_document(
                    str(file_path),
                    str(file_output_dir)
                )
                total_articles += result['articles_count']
                logger.info(f"Processed {file_path.name}: {result['articles_count']} articles")
        
        # Create zip archive
        jobs[job_id]['message'] = "Creating archive..."
        jobs[job_id]['progress'] = 95
        
        zip_path = job_dir / f"{job_id}.zip"
        create_zip_archive(output_base_dir, zip_path)
        
        # Update job status
        jobs[job_id]['status'] = JobStatus.COMPLETED
        jobs[job_id]['message'] = "Processing completed successfully"
        jobs[job_id]['progress'] = 100
        jobs[job_id]['total_articles'] = total_articles
        jobs[job_id]['zip_path'] = zip_path
        
        logger.info(f"Job {job_id} completed. Total articles: {total_articles}")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
        jobs[job_id]['status'] = JobStatus.FAILED
        jobs[job_id]['message'] = "Processing failed"
        jobs[job_id]['error'] = str(e)
        jobs[job_id]['progress'] = 0


@app.post("/upload", response_model=UploadResponse)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    merge_mode: bool = Form(False)
):
    """
    Upload documents for processing.
    
    Args:
        files: List of DOCX or PDF files to process
        merge_mode: If True, merge all files into single output; if False, separate outputs
        
    Returns:
        Job ID for tracking processing status
    """
    cleanup_old_jobs()
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Validate file types
    allowed_extensions = {'.docx', '.pdf'}
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.filename}. Only DOCX and PDF are allowed."
            )
    
    # Create job
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    uploads_dir = job_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    
    # Save uploaded files
    file_paths = []
    for file in files:
        file_path = uploads_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        file_paths.append(file_path)
        logger.info(f"Saved uploaded file: {file.filename}")
    
    # Initialize job state
    jobs[job_id] = {
        'status': JobStatus.PENDING,
        'progress': 0,
        'message': 'Job queued for processing',
        'created_at': datetime.now(),
        'files_count': len(files),
        'merge_mode': merge_mode,
        'total_articles': None,
        'error': None,
        'zip_path': None
    }
    
    # Start background processing
    background_tasks.add_task(
        process_documents_job,
        job_id,
        file_paths,
        merge_mode
    )
    
    logger.info(f"Created job {job_id} with {len(files)} files (merge_mode={merge_mode})")
    
    return UploadResponse(
        job_id=job_id,
        message="Files uploaded successfully. Processing started.",
        files_received=len(files)
    )


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a processing job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Current job status and progress
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    
    return JobStatusResponse(
        job_id=job_id,
        status=job_data['status'],
        progress=job_data['progress'],
        message=job_data['message'],
        total_articles=job_data.get('total_articles'),
        error=job_data.get('error')
    )


@app.get("/download/{job_id}")
async def download_result(job_id: str, background_tasks: BackgroundTasks):
    """
    Download the processed articles as a zip archive.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Zip file with processed markdown files
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    
    if job_data['status'] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job_data['status']}"
        )
    
    zip_path = job_data.get('zip_path')
    if not zip_path or not Path(zip_path).exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    # Schedule cleanup after download
    def cleanup_job():
        logger.info(f"Cleaning up job {job_id} after download")
        job_dir = TEMP_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        if job_id in jobs:
            del jobs[job_id]
    
    background_tasks.add_task(cleanup_job)
    
    return FileResponse(
        path=zip_path,
        media_type='application/zip',
        filename=f'processed_articles_{job_id}.zip'
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "spacy_model_loaded": nlp_model is not None,
        "active_jobs": len(jobs)
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "Legal Document Splitter API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "POST /upload - Upload documents for processing",
            "status": "GET /status/{job_id} - Check job status",
            "download": "GET /download/{job_id} - Download results",
            "health": "GET /health - Health check"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
