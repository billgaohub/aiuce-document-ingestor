"""
Tests for aiuce-document-ingestor.
"""

import tempfile
from pathlib import Path

import pytest

from aiuce_document_ingestor import (
    DocumentIngestor,
    FormatDetector,
    MarkdownNormalizer,
    IngestResult,
    DocFormat,
)


# ─── FormatDetector ──────────────────────────────────────────────────────────

class TestFormatDetector:
    def test_detect_by_extension(self):
        detector = FormatDetector()
        cases = [
            ("doc.pdf", DocFormat.PDF),
            ("doc.docx", DocFormat.WORD),
            ("doc.doc", DocFormat.WORD),
            ("data.xlsx", DocFormat.EXCEL),
            ("data.xls", DocFormat.EXCEL),
            ("slides.pptx", DocFormat.POWERPOINT),
            ("page.html", DocFormat.HTML),
            ("page.htm", DocFormat.HTML),
            ("readme.md", DocFormat.MARKDOWN),
            ("notes.txt", DocFormat.TEXT),
            ("table.csv", DocFormat.CSV),
            ("photo.jpg", DocFormat.IMAGE),
            ("photo.jpeg", DocFormat.IMAGE),
            ("photo.png", DocFormat.IMAGE),
            ("archive.epub", DocFormat.EPUB),
            ("video.mp4", DocFormat.AUDIO),
        ]
        for path, expected in cases:
            assert detector.detect(path) == expected, f"{path} → {detector.detect(path)}, want {expected}"

    def test_detect_unknown_extension(self):
        detector = FormatDetector()
        assert detector.detect("file.xyz") == DocFormat.UNKNOWN

    def test_detect_magic_bytes_pdf(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"%PDF-1.4\n")
            tmp = f.name
        try:
            detector = FormatDetector()
            assert detector.detect(tmp) == DocFormat.PDF
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_detect_magic_bytes_zip(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"PK\x03\x04\x14\x00\x00\x00")
            tmp = f.name
        try:
            detector = FormatDetector()
            assert detector.detect(tmp) == DocFormat.WORD
        finally:
            Path(tmp).unlink(missing_ok=True)


# ─── MarkdownNormalizer ───────────────────────────────────────────────────────

class TestMarkdownNormalizer:
    def test_extract_headings(self):
        md = "# Title\n## Section\n### Subsection\n"
        normalizer = MarkdownNormalizer()
        result = normalizer.normalize(md)
        headings = result["headings"]
        assert len(headings) == 3
        assert headings[0]["level"] == 1
        assert headings[1]["level"] == 2
        assert headings[2]["level"] == 3

    def test_extract_tables(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        normalizer = MarkdownNormalizer()
        result = normalizer.normalize(md)
        assert len(result["tables"]) == 1
        assert result["tables"][0]["rows"][0] == ["A", "B"]

    def test_extract_links(self):
        md = "[Google](https://google.com) and [GitHub](https://github.com)"
        normalizer = MarkdownNormalizer()
        result = normalizer.normalize(md)
        assert len(result["links"]) == 2
        assert result["links"][0]["text"] == "Google"
        assert result["links"][0]["url"] == "https://google.com"

    def test_extract_code_blocks(self):
        md = "```python\nprint('hi')\n```"
        normalizer = MarkdownNormalizer()
        result = normalizer.normalize(md)
        assert len(result["code_blocks"]) == 1
        assert result["code_blocks"][0]["lang"] == "python"
        assert "print" in result["code_blocks"][0]["code"]

    def test_word_char_count(self):
        md = "Hello 世界！ This is 123 test words."
        normalizer = MarkdownNormalizer()
        result = normalizer.normalize(md)
        assert result["word_count"] == 7  # Hello, 世界, This, is, 123, test, words
        assert result["char_count"] == len(md)

    def test_audit_callback_pass(self):
        def always_pass(_):
            return {"passed": True, "reason": ""}

        normalizer = MarkdownNormalizer(audit_callback=always_pass)
        result = normalizer.normalize("# Doc\n\nHello")
        assert result["passed"] is True
        assert result["reason"] == ""

    def test_audit_callback_fail(self):
        def reject_on_word(content):
            if "BLOCKED" in content:
                return {"passed": False, "reason": "contains BLOCKED"}
            return {"passed": True, "reason": ""}

        normalizer = MarkdownNormalizer(audit_callback=reject_on_word)
        result = normalizer.normalize("# Doc\n\nThis is BLOCKED content.")
        assert result["passed"] is False
        assert "BLOCKED" in result["reason"]


# ─── DocumentIngestor ─────────────────────────────────────────────────────────

class TestDocumentIngestor:
    def test_ingest_text_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Title\n\nParagraph one.\n\nParagraph two.")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            assert isinstance(result, IngestResult)
            assert result.format == DocFormat.TEXT
            assert result.word_count > 0
            assert "Title" in result.markdown_content
            assert result.passed is True
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_ingest_markdown_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Hello\n\n## World\n\nContent here.")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            assert result.format == DocFormat.MARKDOWN
            assert result.headings == ["Hello", "World"]
            assert result.word_count > 0
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_ingest_csv_file(self):
        with tempfile.NamedTemporaryFile(
            suffix=".csv", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("Name,Score\nAlice,90\nBob,85\n")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            assert result.format == DocFormat.CSV
            assert result.word_count > 0
            # Markdown should contain a table
            assert "|" in result.markdown_content
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_ingest_batch(self):
        tmp_files = []
        try:
            for i in range(3):
                with tempfile.NamedTemporaryFile(
                    suffix=".txt", mode="w", delete=False, encoding="utf-8"
                ) as f:
                    f.write(f"# Doc {i}\n\nContent {i}.")
                    tmp_files.append(f.name)

            ingestor = DocumentIngestor()
            results = ingestor.ingest_batch(tmp_files)
            assert len(results) == 3
            for r in results:
                assert r.format == DocFormat.TEXT
                assert r.word_count > 0
        finally:
            for p in tmp_files:
                Path(p).unlink(missing_ok=True)

    def test_ingest_nonexistent_raises(self):
        ingestor = DocumentIngestor()
        with pytest.raises(FileNotFoundError):
            ingestor.ingest("/nonexistent/path/to/file.xyz")

    def test_ingest_unknown_format(self):
        # A file with an unknown extension
        with tempfile.NamedTemporaryFile(suffix=".xyz", mode="w", delete=False) as f:
            f.write("some content")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            assert result.format == DocFormat.UNKNOWN
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_ingest_result_to_dict(self):
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Title\n\nHello world.")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            d = result.to_dict()
            assert isinstance(d, dict)
            assert d["format"] == DocFormat.TEXT
            assert d["word_count"] > 0
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_structured_json_has_required_keys(self):
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Title\n\nParagraph.\n")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            json_out = result.structured_json
            for key in ("headings", "tables", "links", "code_blocks",
                        "word_count", "char_count", "format"):
                assert key in json_out, f"Missing key: {key}"
        finally:
            Path(tmp).unlink(missing_ok=True)


# ─── IngestResult fields ─────────────────────────────────────────────────────

class TestIngestResultFields:
    def test_default_passes_is_true(self):
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("hello")
            tmp = f.name
        try:
            ingestor = DocumentIngestor()
            result = ingestor.ingest(tmp)
            assert result.passed is True
            assert result.reason == ""
        finally:
            Path(tmp).unlink(missing_ok=True)

    def test_audit_sets_reason_on_failure(self):
        def always_fail(_):
            return {"passed": False, "reason": "audit failed"}

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("hello")
            tmp = f.name
        try:
            ingestor = DocumentIngestor(audit_callback=always_fail)
            result = ingestor.ingest(tmp)
            assert result.passed is False
            assert result.reason == "audit failed"
        finally:
            Path(tmp).unlink(missing_ok=True)
