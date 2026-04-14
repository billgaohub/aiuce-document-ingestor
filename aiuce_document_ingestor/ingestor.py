"""
AIUCE Document Ingestor — main ingestor module

Converts various document formats (PDF, Word, Excel, PowerPoint, HTML,
Markdown, text, CSV, images) into Markdown, with structured JSON output
suitable for AI consumption.

External dependencies:
    - markitdown  (pip install markitdown)  — preferred converter
    - pdftotext   (poppler-utils)            — fallback for PDF
    - pandoc                                  — fallback for HTML
    - tesseract   (tesseract-ocr)             — image OCR
"""

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

from .types import DocFormat, IngestResult
from .detector import FormatDetector
from .normalizer import MarkdownNormalizer

logger = logging.getLogger(__name__)


class DocumentIngestor:
    """
    Universal document ingestion pipeline.

    Converts documents to Markdown and produces dual-track output:
    - markdown_content  — human-readable Markdown
    - structured_json    — machine-readable structured data

    Args:
        audit_callback: Optional callable(content: str) -> dict with keys
                        'passed' (bool) and 'reason' (str). Used to apply
                        custom content policy checks.
        use_llm_ocr:    Enable LLM-powered OCR (requires markitdown with
                        an OPENAI_API_KEY or ANTHROPIC_API_KEY in the
                        environment). Has no effect if markitdown is not
                        installed.
    """

    def __init__(
        self,
        audit_callback: Optional[Callable[[str], Dict[str, Any]]] = None,
        use_llm_ocr: bool = False,
    ):
        self._detector = FormatDetector()
        self._normalizer = MarkdownNormalizer(audit_callback=audit_callback)
        self._use_llm_ocr = use_llm_ocr

    # ── Public API ────────────────────────────────────────────────

    def ingest(
        self,
        path_or_url: str,
        source_url: Optional[str] = None,
        max_tables: int = 50,
    ) -> IngestResult:
        """
        Ingest a single document.

        Args:
            path_or_url: File path or HTTP(S) URL.
            source_url:  Original URL to record (used when path_or_url
                         is a local copy of a URL).
            max_tables:  Maximum number of tables to include in output.

        Returns:
            IngestResult with Markdown content and structured metadata.
        """
        path = path_or_url

        # ── URL handling ──────────────────────────────────────
        if path.startswith("http://") or path.startswith("https://"):
            source_url = path
            path = self._download_url(path)

        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        fmt = self._detector.detect(path)
        logger.info("Ingesting %s (format: %s)", path, fmt.value)

        # ── Format conversion ────────────────────────────────
        if fmt == DocFormat.MARKDOWN:
            raw_markdown = Path(path).read_text(encoding="utf-8")
        elif fmt == DocFormat.TEXT:
            raw_markdown = self._text_to_markdown(path)
        elif fmt == DocFormat.PDF:
            raw_markdown = self._convert_pdf(path, use_llm=self._use_llm_ocr)
        elif fmt in (DocFormat.WORD, DocFormat.EXCEL, DocFormat.POWERPOINT):
            raw_markdown = self._convert_office(path)
        elif fmt == DocFormat.HTML:
            raw_markdown = self._html_to_markdown(path)
        elif fmt == DocFormat.IMAGE:
            raw_markdown = self._ocr_image(path, use_llm=self._use_llm_ocr)
        elif fmt == DocFormat.CSV:
            raw_markdown = self._csv_to_markdown(path)
        else:
            raw_markdown = f"# Document\n\n[Unsupported format: {fmt.value}]"

        # ── Normalization ────────────────────────────────────
        normalized = self._normalizer.normalize(raw_markdown, path)

        # ── Dual-track output ────────────────────────────────
        return IngestResult(
            format=fmt,
            file_path=path,
            markdown_content=raw_markdown,
            structured_json={
                "headings": normalized["headings"],
                "tables": normalized["tables"][:max_tables],
                "links": normalized["links"],
                "code_blocks": normalized["code_blocks"],
                "word_count": normalized["word_count"],
                "char_count": normalized["char_count"],
                "format": fmt.value,
            },
            word_count=normalized["word_count"],
            char_count=normalized["char_count"],
            tables=normalized["tables"][:max_tables],
            headings=[h["text"] for h in normalized["headings"]],
            links=[l["url"] for l in normalized["links"]],
            images=[],  # placeholder; markitdown handles image extraction
            source_url=source_url,
            ingested_at=normalized.get("ingested_at", ""),
            passed=normalized["passed"],
            reason=normalized["reason"],
        )

    def ingest_batch(
        self,
        paths: List[str],
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[IngestResult]:
        """
        Ingest multiple documents.

        Args:
            paths:       List of file paths or URLs.
            on_progress: Optional callback(path, current, total) called
                        after each file completes.
        """
        results: List[IngestResult] = []
        for i, path in enumerate(paths, 1):
            try:
                result = self.ingest(path)
                results.append(result)
            except Exception as exc:
                logger.error("Failed to ingest %s: %s", path, exc)
                results.append(IngestResult(
                    format=DocFormat.UNKNOWN,
                    file_path=path,
                    markdown_content="",
                    structured_json={"error": str(exc)},
                    word_count=0,
                    char_count=0,
                ))
            if on_progress:
                on_progress(path, i, len(paths))
        return results

    # ── Internal converters ────────────────────────────────────────

    def _has_markitdown(self) -> bool:
        """Check whether the `markitdown` CLI is installed."""
        try:
            r = subprocess.run(
                ["markitdown", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _convert_pdf(self, path: str, use_llm: bool = False) -> str:
        """Convert PDF to Markdown using markitdown or pdftotext."""
        if self._has_markitdown():
            try:
                r = subprocess.run(
                    ["markitdown", path],
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    return r.stdout
            except Exception as exc:
                logger.warning("markitdown failed: %s — falling back", exc)

        # Fallback: pdftotext
        try:
            r = subprocess.run(
                ["pdftotext", "-layout", path, "-"],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0:
                return self._plaintext_to_markdown(r.stdout)
        except Exception:
            pass

        return f"# PDF Document\n\n[Failed to extract text from PDF: {path}]"

    def _convert_office(self, path: str) -> str:
        """Convert Office documents (docx/xlsx/pptx) to Markdown using markitdown."""
        if self._has_markitdown():
            try:
                r = subprocess.run(
                    ["markitdown", path],
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    return r.stdout
            except Exception as exc:
                logger.warning("markitdown failed: %s", exc)

        return f"# Office Document\n\n[markitdown not installed: {path}]"

    def _html_to_markdown(self, path: str) -> str:
        """Convert HTML to Markdown using pandoc, with a regex fallback."""
        try:
            r = subprocess.run(
                ["pandoc", "-f", "html", "-t", "markdown", path],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return r.stdout
        except Exception:
            pass

        # Regex fallback
        try:
            html = Path(path).read_text(encoding="utf-8")
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"&nbsp;", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return f"# Web Page\n\n{text}"
        except Exception:
            return f"# HTML Document\n\n[Failed to parse: {path}]"

    def _text_to_markdown(self, path: str) -> str:
        """Read plain text and wrap it in minimal Markdown."""
        text = Path(path).read_text(encoding="utf-8")
        return f"# Document\n\n{text}"

    @staticmethod
    def _plaintext_to_markdown(text: str) -> str:
        """Split plain text into paragraphs and return as Markdown."""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        return "\n\n".join(paragraphs)

    def _csv_to_markdown(self, path: str) -> str:
        """Convert a CSV file to a Markdown table."""
        try:
            import csv
            with open(path, encoding="utf-8") as f:
                rows = list(csv.reader(f))
            if not rows:
                return "# CSV\n\n[Empty]"
            header = rows[0]
            md_lines = ["| " + " | ".join(header) + " |"]
            md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in rows[1:]:
                md_lines.append("| " + " | ".join(row[:len(header)]) + " |")
            return f"# CSV: {Path(path).name}\n\n" + "\n".join(md_lines)
        except Exception as exc:
            return f"# CSV\n\n[Failed to parse: {exc}]"

    def _ocr_image(self, path: str, use_llm: bool = False) -> str:
        """Run OCR on an image using tesseract or LLM."""
        if use_llm:
            return "[LLM OCR requires OPENAI_API_KEY or ANTHROPIC_API_KEY]"
        try:
            r = subprocess.run(
                ["tesseract", path, "stdout", "-l", "chi_sim+eng"],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0:
                return f"# Image OCR\n\n{r.stdout}"
        except Exception:
            pass
        return f"# Image\n\n[OCR not available: {path}]"

    def _download_url(self, url: str) -> str:
        """Download a URL to a local temporary file and return its path."""
        try:
            import urllib.request
            tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
            urllib.request.urlretrieve(url, tmp.name)
            tmp.close()
            return tmp.name
        except Exception as exc:
            raise RuntimeError(f"Failed to download {url}: {exc}")
