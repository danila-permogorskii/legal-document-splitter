import pdfplumber
from docx import Document as DocxDocument
from typing import Optional


class TextExtractor:
    """Base class for text extraction from various document formats."""
    
    @staticmethod
    def extract_from_docx(file_path: str) -> str:
        """
        Extract text from DOCX file.
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            Full text content as string
        """
        doc = DocxDocument(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    
    @staticmethod
    def extract_from_pdf(file_path: str) -> str:
        """
        Extract text from PDF file using pdfplumber.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Full text content as string
        """
        full_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
        return '\n'.join(full_text)
    
    @staticmethod
    def extract_text(file_path: str) -> str:
        """
        Auto-detect file type and extract text.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Full text content as string
            
        Raises:
            ValueError: If file format is not supported
        """
        file_path_lower = file_path.lower()
        
        if file_path_lower.endswith('.docx'):
            return TextExtractor.extract_from_docx(file_path)
        elif file_path_lower.endswith('.pdf'):
            return TextExtractor.extract_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
