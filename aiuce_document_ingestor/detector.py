"""
AIUCE Document Ingestor — format detector module
"""

from pathlib import Path
from typing import Dict

from .types import DocFormat


class FormatDetector:
    """
    Detect document format from file extension and magic bytes.
    """

    FORMAT_MAP: Dict[str, DocFormat] = {
        ".pdf": DocFormat.PDF,
        ".docx": DocFormat.WORD,
        ".doc": DocFormat.WORD,
        ".xlsx": DocFormat.EXCEL,
        ".xls": DocFormat.EXCEL,
        ".pptx": DocFormat.POWERPOINT,
        ".ppt": DocFormat.POWERPOINT,
        ".html": DocFormat.HTML,
        ".htm": DocFormat.HTML,
        ".md": DocFormat.MARKDOWN,
        ".txt": DocFormat.TEXT,
        ".csv": DocFormat.CSV,
        ".json": DocFormat.JSON,
        ".jpg": DocFormat.IMAGE,
        ".jpeg": DocFormat.IMAGE,
        ".png": DocFormat.IMAGE,
        ".gif": DocFormat.IMAGE,
        ".mp3": DocFormat.AUDIO,
        ".mp4": DocFormat.AUDIO,
        ".epub": DocFormat.EPUB,
    }

    MAGIC_BYTES: Dict[bytes, DocFormat] = {
        b"%PDF": DocFormat.PDF,
        b"PK\x03\x04": DocFormat.WORD,  # docx/xlsx/pptx are ZIP-based
        b"<!DOCTYPE": DocFormat.HTML,
        b"<html": DocFormat.HTML,
    }

    @classmethod
    def detect(cls, path: str) -> DocFormat:
        """Detect the format of a file."""
        ext = Path(path).suffix.lower()
        if ext in cls.FORMAT_MAP:
            return cls.FORMAT_MAP[ext]

        # Magic bytes detection
        try:
            with open(path, "rb") as f:
                header = f.read(16)
            for magic, fmt in cls.MAGIC_BYTES.items():
                if header.startswith(magic):
                    return fmt
        except Exception:
            pass

        return DocFormat.UNKNOWN
