from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadResponse(BaseModel):
    job_id: str
    message: str
    files_received: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int
    message: str
    total_articles: Optional[int] = None
    error: Optional[str] = None


class ArticleMetadata(BaseModel):
    article_title: str
    section_title: Optional[str] = None
    chapter_title: Optional[str] = None
    paragraph_title: Optional[str] = None
    keywords: List[str] = []
    topic: str = ""
