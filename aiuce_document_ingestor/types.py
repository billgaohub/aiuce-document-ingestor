"""
AIUCE Document Ingestor — types module
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class DocFormat(Enum):
    """Supported document formats."""
    PDF = "pdf"
    WORD = "docx"
    EXCEL = "xlsx"
    POWERPOINT = "pptx"
    HTML = "html"
    MARKDOWN = "md"
    TEXT = "txt"
    CSV = "csv"
    JSON = "json"
    IMAGE = "image"      # OCR
    AUDIO = "audio"      # speech transcription
    YOUTUBE = "youtube"  # YouTube subtitles
    EPUB = "epub"
    UNKNOWN = "unknown"


@dataclass
class IngestResult:
    """Result of a document ingestion operation."""
    format: DocFormat
    file_path: str
    markdown_content: str
    structured_json: Dict[str, Any]
    word_count: int
    char_count: int
    tables: List[Dict[str, Any]] = field(default_factory=list)
    headings: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    ingested_at: str = field(default_factory=datetime.now().isoformat)
    passed: bool = True
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
