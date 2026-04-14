"""
Basic usage examples for aiuce-document-ingestor.
"""

import tempfile
from pathlib import Path

from aiuce_document_ingestor import (
    DocumentIngestor,
    FormatDetector,
    MarkdownNormalizer,
    DocFormat,
)


def example_detector():
    """Show how FormatDetector works."""
    detector = FormatDetector()

    cases = [
        ("document.pdf", DocFormat.PDF),
        ("report.docx", DocFormat.WORD),
        ("data.xlsx", DocFormat.EXCEL),
        ("slides.pptx", DocFormat.POWERPOINT),
        ("page.html", DocFormat.HTML),
        ("notes.md", DocFormat.MARKDOWN),
        ("readme.txt", DocFormat.TEXT),
        ("table.csv", DocFormat.CSV),
        ("photo.png", DocFormat.IMAGE),
        ("unknown.xyz", DocFormat.UNKNOWN),
    ]

    print("=== FormatDetector ===")
    for path, expected in cases:
        detected = detector.detect(path)
        status = "✓" if detected == expected else f"✗ (expected {expected.value})"
        print(f"  {path:20s} → {detected.value:10s} {status}")


def example_normalizer():
    """Show how MarkdownNormalizer extracts structured data."""
    sample = """\
# Main Title

Some introductory paragraph.

## Section One

- Item A
- Item B

### Subsection

| Column A | Column B |
|----------|----------|
| Cell 1   | Cell 2   |

[Link Text](https://example.com)

```python
print("hello")
```
"""
    normalizer = MarkdownNormalizer()
    result = normalizer.normalize(sample, source_path="example.md")

    print("\n=== MarkdownNormalizer ===")
    print(f"  Headings: {[h['text'] for h in result['headings']]}")
    print(f"  Tables:   {len(result['tables'])} table(s)")
    print(f"  Links:    {result['links']}")
    print(f"  Code:     {len(result['code_blocks'])} block(s)")
    print(f"  Words:    {result['word_count']}")
    print(f"  Chars:    {result['char_count']}")
    print(f"  Passed:   {result['passed']}")


def example_audit_callback():
    """Show how to wire in a custom content audit."""

    def sensitive_audit(content: str):
        forbidden = ["CONFIDENTIAL", "TOP SECRET", "INTERNAL ONLY"]
        for keyword in forbidden:
            if keyword in content:
                return {"passed": False, "reason": f"Found forbidden keyword: {keyword}"}
        return {"passed": True, "reason": ""}

    normalizer = MarkdownNormalizer(audit_callback=sensitive_audit)

    ok_result = normalizer.normalize("# Public Note\n\nThis is fine.")
    print(f"\n=== Audit (clean) ===  passed={ok_result['passed']}")

    bad_result = normalizer.normalize("# Memo\n\nCONFIDENTIAL: do not share.")
    print(f"=== Audit (flagged) ===  passed={bad_result['passed']}, reason={bad_result['reason']}")


def example_ingestor_text():
    """Show full ingestion pipeline with a plain-text file."""
    with tempfile.NamedTemporaryFile(
        suffix=".txt", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("# Project Report\n\n## Overview\n\nThis is a plain-text document.\n\n## Data\n\n| Name   | Value |\n|--------|-------|\n| Alice  | 100   |\n| Bob    | 200   |\n")
        tmp_path = f.name

    try:
        ingestor = DocumentIngestor()
        result = ingestor.ingest(tmp_path)

        print("\n=== DocumentIngestor (text file) ===")
        print(f"  Format:    {result.format.value}")
        print(f"  File:      {result.file_path}")
        print(f"  Headings:  {result.headings}")
        print(f"  Tables:    {len(result.tables)}")
        print(f"  Word count:{result.word_count}")
        print(f"  Passed:    {result.passed}")
        print("\n  Markdown preview:")
        for line in result.markdown_content.splitlines()[:10]:
            print(f"    {line}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def example_batch():
    """Show batch ingestion with progress callback."""
    # Create two temp text files
    tmp_files = []
    try:
        for i in range(2):
            with tempfile.NamedTemporaryFile(
                suffix=".txt", mode="w", delete=False, encoding="utf-8"
            ) as f:
                f.write(f"# Document {i + 1}\n\nContent of document {i + 1}.\n")
                tmp_files.append(f.name)

        ingestor = DocumentIngestor()
        collected = []

        def on_progress(path, current, total):
            collected.append((current, total, path))
            print(f"  progress: [{current}/{total}] {path}")

        print("\n=== Batch ingestion ===")
        results = ingestor.ingest_batch(tmp_files, on_progress=on_progress)

        for r in results:
            print(f"  -> {r.format.value}: {r.word_count} words, passed={r.passed}")
    finally:
        for p in tmp_files:
            Path(p).unlink(missing_ok=True)


if __name__ == "__main__":
    example_detector()
    example_normalizer()
    example_audit_callback()
    example_ingestor_text()
    example_batch()
