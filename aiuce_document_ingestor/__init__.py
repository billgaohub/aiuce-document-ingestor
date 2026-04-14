"""
aiuce-document-ingestor
~~~~~~~~~~~~~~~~~~~~~~~

Universal document ingestion: PDF, Word, Excel, PowerPoint, HTML,
Markdown, CSV, images → Markdown + structured JSON.
"""

from .types import DocFormat, IngestResult
from .detector import FormatDetector
from .normalizer import MarkdownNormalizer
from .ingestor import DocumentIngestor

__version__ = "0.1.0"
__all__ = [
    "DocFormat",
    "IngestResult",
    "FormatDetector",
    "MarkdownNormalizer",
    "DocumentIngestor",
]
