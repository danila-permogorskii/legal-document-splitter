import os
import re
import spacy
from collections import Counter
from typing import List, Dict, Tuple, Optional
from langchain.schema import Document
from extractors import TextExtractor
import logging

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process legal documents: extract text, split into articles, extract keywords."""
    
    def __init__(self, nlp_model: Optional[spacy.language.Language] = None):
        """
        Initialize the processor.
        
        Args:
            nlp_model: Pre-loaded SpaCy model. If None, will load ru_core_news_sm
        """
        if nlp_model is None:
            try:
                self.nlp = spacy.load('ru_core_news_sm')
                logger.info("Russian SpaCy model 'ru_core_news_sm' loaded successfully.")
            except OSError:
                logger.error("Russian SpaCy model 'ru_core_news_sm' not found.")
                raise RuntimeError(
                    "SpaCy model not found. Please install it using: "
                    "python -m spacy download ru_core_news_sm"
                )
        else:
            self.nlp = nlp_model
        
        # Regex patterns for structure detection
        self.article_start_pattern = re.compile(
            r'^\s*Статья\s*\d+(?:\.\d+)*\.?\s*(.*)', 
            re.IGNORECASE
        )
        self.section_start_pattern = re.compile(
            r'^\s*Раздел\s+\d+\.?\s*(.*)', 
            re.IGNORECASE
        )
        self.chapter_start_pattern = re.compile(
            r'^\s*Глава\s+\d+\.?\s*(.*)', 
            re.IGNORECASE
        )
        self.paragraph_start_pattern = re.compile(
            r'^\s*§\s+\d+\.?\s*(.*)', 
            re.IGNORECASE
        )
    
    def extract_text_from_file(self, file_path: str) -> str:
        """Extract text from DOCX or PDF file."""
        return TextExtractor.extract_text(file_path)
    
    def segment_into_articles(self, doc_text: str) -> List[Document]:
        """
        Segment document text into articles with hierarchical metadata.
        
        Args:
            doc_text: Full document text
            
        Returns:
            List of LangChain Document objects with article content and metadata
        """
        spacy_doc = self.nlp(doc_text)
        logger.info(f"Document processed by SpaCy. Total sentences: {len(list(spacy_doc.sents))}")
        
        langchain_articles = []
        current_article_full_title = None
        current_article_content = []
        current_section_title = None
        current_chapter_title = None
        current_paragraph_title = None
        
        def add_article_to_list():
            nonlocal current_article_full_title, current_article_content
            nonlocal current_section_title, current_chapter_title, current_paragraph_title
            
            if current_article_full_title and current_article_content:
                full_content_str = "\n".join(current_article_content).strip()
                metadata = {'article_title': current_article_full_title}
                
                if current_section_title:
                    metadata['section_title'] = current_section_title
                if current_chapter_title:
                    metadata['chapter_title'] = current_chapter_title
                if current_paragraph_title:
                    metadata['paragraph_title'] = current_paragraph_title
                
                langchain_articles.append(
                    Document(page_content=full_content_str, metadata=metadata)
                )
            
            current_article_full_title = None
            current_article_content = []
        
        for sent in spacy_doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            
            section_match = self.section_start_pattern.match(sent_text)
            chapter_match = self.chapter_start_pattern.match(sent_text)
            paragraph_match = self.paragraph_start_pattern.match(sent_text)
            article_match = self.article_start_pattern.match(sent_text)
            
            if section_match:
                add_article_to_list()
                current_section_title = section_match.group(0).strip()
                current_chapter_title = None
                current_paragraph_title = None
            elif chapter_match:
                add_article_to_list()
                current_chapter_title = chapter_match.group(0).strip()
                current_paragraph_title = None
            elif paragraph_match:
                add_article_to_list()
                current_paragraph_title = paragraph_match.group(0).strip()
            elif article_match:
                add_article_to_list()
                current_article_full_title = article_match.group(0).strip()
                current_article_content.append(sent_text)
            else:
                if current_article_full_title:
                    current_article_content.append(sent_text)
        
        add_article_to_list()
        logger.info(f"Found {len(langchain_articles)} articles.")
        
        return langchain_articles
    
    def extract_keywords_and_topic(
        self, 
        text: str, 
        article_title: str, 
        num_keywords: int = 7
    ) -> Tuple[List[str], str]:
        """
        Extract keywords and determine topic from article text.
        
        Args:
            text: Article content
            article_title: Title of the article
            num_keywords: Number of keywords to extract
            
        Returns:
            Tuple of (keywords list, topic string)
        """
        doc = self.nlp(text)
        candidates = Counter()
        
        title_tokens = set(
            token.lemma_.lower() 
            for token in self.nlp(article_title) 
            if not token.is_stop and not token.is_punct and not token.like_num
        )
        
        for token in doc:
            if not token.is_stop and not token.is_punct and not token.like_num and token.text.strip():
                lemma = token.lemma_.lower()
                if lemma not in title_tokens:
                    candidates[lemma] += 1
        
        filtered_candidates = []
        for item, count in candidates.most_common():
            if len(item) > 2 and item not in title_tokens:
                filtered_candidates.append(item)
        
        keywords = filtered_candidates[:num_keywords]
        
        topic = keywords[0] if keywords else "Общее положение"
        
        return keywords, topic
    
    def enrich_articles_with_metadata(self, articles: List[Document]) -> List[Document]:
        """
        Add keywords and topics to article metadata.
        
        Args:
            articles: List of Document objects
            
        Returns:
            Same list with enriched metadata
        """
        logger.info("Extracting keywords and topics...")
        
        for article_doc in articles:
            text_content = article_doc.page_content
            article_title = article_doc.metadata.get('article_title', '')
            
            keywords, topic = self.extract_keywords_and_topic(text_content, article_title)
            
            article_doc.metadata['keywords'] = keywords
            article_doc.metadata['topic'] = topic
        
        logger.info(f"Successfully extracted keywords and topics for {len(articles)} articles.")
        return articles
    
    @staticmethod
    def sanitize_string_for_filename(text: str, max_length: int = 200) -> str:
        """Sanitize string for safe filename use."""
        sanitized = re.sub(r'[\\/:*?"<>|]', '', text)
        sanitized = sanitized.replace(' ', '_').strip()
        return sanitized[:max_length]
    
    @staticmethod
    def get_structure_filename_id(title: str, prefix: str, max_length: int = 50) -> str:
        """Extract structural identifier from title for filename."""
        match = re.search(
            r'(' + re.escape(prefix) + r'\s*\d+(?:\.\d+)*)', 
            title, 
            re.IGNORECASE
        )
        if match:
            return DocumentProcessor.sanitize_string_for_filename(
                match.group(1), 
                max_length=max_length
            )
        return ""
    
    def save_articles_to_markdown(
        self, 
        articles: List[Document], 
        output_dir: str,
        doc_base_name: str = "document"
    ) -> List[str]:
        """
        Save articles as individual markdown files.
        
        Args:
            articles: List of Document objects with content and metadata
            output_dir: Directory to save markdown files
            doc_base_name: Base name for the document (used in filenames)
            
        Returns:
            List of created file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Output directory '{output_dir}' created or already exists.")
        
        sanitized_doc_name_prefix = self.sanitize_string_for_filename(
            doc_base_name, 
            max_length=40
        )
        
        created_files = []
        
        for i, article_doc in enumerate(articles):
            full_article_title = article_doc.metadata.get(
                "article_title", 
                f"Untitled_Article_{i+1}"
            )
            content = article_doc.page_content
            keywords = article_doc.metadata.get("keywords", [])
            topic = article_doc.metadata.get("topic", "")
            section_title = article_doc.metadata.get("section_title", "")
            chapter_title = article_doc.metadata.get("chapter_title", "")
            paragraph_title = article_doc.metadata.get("paragraph_title", "")
            
            markdown_content = f"# {full_article_title}\n\n"
            if section_title:
                markdown_content += f"## {section_title}\n\n"
            if chapter_title:
                markdown_content += f"### {chapter_title}\n\n"
            if paragraph_title:
                markdown_content += f"#### {paragraph_title}\n\n"
            markdown_content += f"{content}\n\n"
            if keywords:
                markdown_content += f"## Keywords\n{', '.join(keywords)}\n\n"
            if topic:
                markdown_content += f"## Topic\n{topic}\n"
            
            filename_parts = [sanitized_doc_name_prefix]
            
            if section_title:
                filename_parts.append(
                    self.get_structure_filename_id(section_title, "Раздел")
                )
            if chapter_title:
                filename_parts.append(
                    self.get_structure_filename_id(chapter_title, "Глава")
                )
            if paragraph_title:
                filename_parts.append(
                    self.get_structure_filename_id(paragraph_title, "§")
                )
            
            article_id_part = self.get_structure_filename_id(full_article_title, "Статья")
            if article_id_part:
                filename_parts.append(article_id_part)
            
            descriptive_title_raw = re.sub(
                r'^\s*Статья\s*\d+(?:\.\d+)*\.?\s*', 
                '', 
                full_article_title, 
                flags=re.IGNORECASE
            ).strip()
            
            if descriptive_title_raw:
                descriptive_title_sanitized = self.sanitize_string_for_filename(
                    descriptive_title_raw, 
                    max_length=50
                )
                if descriptive_title_sanitized:
                    filename_parts.append(descriptive_title_sanitized)
            
            if keywords:
                keyword_segment = "_".join(
                    self.sanitize_string_for_filename(k, max_length=20) 
                    for k in keywords[:2]
                )
                if keyword_segment:
                    filename_parts.append(keyword_segment)
            
            filename = "_".join(filter(None, filename_parts)) + ".md"
            
            max_total_filename_length = 200
            if len(filename) > max_total_filename_length:
                base, ext = os.path.splitext(filename)
                filename = base[:max_total_filename_length - len(ext)] + ext
            
            file_path = os.path.join(output_dir, filename)
            
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                created_files.append(file_path)
            except OSError as e:
                logger.warning(f"Error saving file '{file_path}': {e}")
                fallback_filename = f"{sanitized_doc_name_prefix}_Article_{i+1}.md"
                fallback_file_path = os.path.join(output_dir, fallback_filename)
                logger.info(f"Attempting fallback filename: '{fallback_file_path}'")
                try:
                    with open(fallback_file_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    created_files.append(fallback_file_path)
                except OSError as fallback_e:
                    logger.error(f"Fallback failed for '{full_article_title}': {fallback_e}")
                    continue
        
        logger.info(f"Successfully saved {len(created_files)} articles as markdown files.")
        return created_files
    
    def process_document(
        self, 
        file_path: str, 
        output_dir: str
    ) -> Dict:
        """
        Complete processing pipeline for a single document.
        
        Args:
            file_path: Path to input document (DOCX or PDF)
            output_dir: Directory for output markdown files
            
        Returns:
            Dict with processing results
        """
        doc_base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        logger.info(f"Processing document: {file_path}")
        doc_text = self.extract_text_from_file(file_path)
        logger.info(f"Extracted {len(doc_text)} characters from document.")
        
        articles = self.segment_into_articles(doc_text)
        articles = self.enrich_articles_with_metadata(articles)
        
        created_files = self.save_articles_to_markdown(
            articles, 
            output_dir, 
            doc_base_name
        )
        
        return {
            'document': doc_base_name,
            'articles_count': len(articles),
            'files_created': len(created_files),
            'output_dir': output_dir
        }
