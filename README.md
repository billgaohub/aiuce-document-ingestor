# aiuce-document-ingestor

**Universal document ingestion: convert any document to Markdown + structured JSON.**

```bash
pip install aiuce-document-ingestor
```

## Features

- **Multi-format support** — PDF, Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), HTML, Markdown, plain text, CSV, images (OCR), EPUB
- **Dual-track output** — Markdown for humans, structured JSON for AI pipelines
- **Automatic format detection** — extension-based with magic-byte fallback
- **Markdown normalization** — extracts headings, tables, links, code blocks
- **Optional content audit** — plug in a custom callback to enforce content policy
- **Batch ingestion** — process multiple files with a progress callback

## Quick Start

```python
from aiuce_document_ingestor import DocumentIngestor

ingestor = DocumentIngestor()
result = ingestor.ingest("report.pdf")

print(result.markdown_content)  # human-readable
print(result.structured_json)   # machine-readable
print(result.word_count)
```

## Supported Formats

| Format      | Extension(s)            | Converter            |
|-------------|-------------------------|----------------------|
| PDF         | `.pdf`                  | markitdown / pdftotext |
| Word        | `.docx`, `.doc`         | markitdown           |
| Excel       | `.xlsx`, `.xls`         | markitdown           |
| PowerPoint  | `.pptx`, `.ppt`         | markitdown           |
| HTML        | `.html`, `.htm`         | pandoc / regex       |
| Markdown    | `.md`                   | direct read          |
| Plain text  | `.txt`                  | direct read          |
| CSV         | `.csv`                  | built-in CSV parser  |
| Image       | `.jpg`, `.jpeg`, `.png`, `.gif` | tesseract OCR |
| EPUB        | `.epub`                 | markitdown           |

> **Note:** [markitdown](https://github.com/microsoft/markitdown) is the preferred converter.
> Install it with `pip install markitdown` or via system package manager.
> Fallback converters (pdftotext, pandoc, tesseract) are used when markitdown is unavailable.

## Installation

```bash
# Core package
pip install aiuce-document-ingestor

# Optional: recommended converter
pip install markitdown

# Optional: OCR support
# macOS
brew install tesseract tesseract-lang
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

## Usage

### Single file

```python
from aiuce_document_ingestor import DocumentIngestor

ingestor = DocumentIngestor()
result = ingestor.ingest("document.docx")

print(result.markdown_content)   # Markdown string
print(result.structured_json)    # dict with headings, tables, links, ...
print(result.word_count)
print(result.tables)             # list of extracted tables
print(result.headings)            # list of heading texts
```

### Batch ingestion

```python
from aiuce_document_ingestor import DocumentIngestor

ingestor = DocumentIngestor()

def on_progress(path, current, total):
    print(f"[{current}/{total}] {path}")

results = ingestor.ingest_batch(
    ["doc1.pdf", "doc2.docx", "doc3.html"],
    on_progress=on_progress,
)

for r in results:
    print(r.format, r.file_path, r.word_count)
```

### Content audit callback

```python
def my_audit(content: str) -> dict:
    if "CONFIDENTIAL" in content:
        return {"passed": False, "reason": "Contains CONFIDENTIAL marker"}
    return {"passed": True, "reason": ""}

ingestor = DocumentIngestor(audit_callback=my_audit)
result = ingestor.ingest("memo.pdf")
print(result.passed, result.reason)
```

### URL ingestion

```python
result = ingestor.ingest("https://example.com/article.html")
print(result.source_url)
```

## API Reference

### `DocumentIngestor`

```python
DocumentIngestor(audit_callback=None, use_llm_ocr=False)
```

| Parameter       | Type                                      | Description                                    |
|-----------------|-------------------------------------------|------------------------------------------------|
| `audit_callback`| `Callable[[str], dict]` \| `None`        | Optional content audit hook. Receives plain text, returns `{"passed": bool, "reason": str}`. |
| `use_llm_ocr`   | `bool`                                   | Enable LLM OCR via markitdown (requires API key env var). Default `False`. |

### `ingest(path_or_url, source_url=None, max_tables=50) -> IngestResult`

Ingest a single document. See method docstring for details.

### `ingest_batch(paths, on_progress=None) -> List[IngestResult]`

Ingest multiple documents. See method docstring for details.

### `IngestResult`

```python
@dataclass
class IngestResult:
    format: DocFormat
    file_path: str
    markdown_content: str
    structured_json: dict      # headings, tables, links, code_blocks, word_count, char_count
    word_count: int
    char_count: int
    tables: List[dict]          # extracted tables [{'rows': [[cell, ...], ...]}]
    headings: List[str]         # extracted heading texts
    images: List[str]           # image paths (placeholder)
    links: List[str]            # extracted URLs
    source_url: str | None
    ingested_at: str            # ISO timestamp
    passed: bool                # True unless audit_callback returned passed=False
    reason: str                 # veto reason if passed=False
```

### `DocFormat` Enum

```python
class DocFormat(Enum):
    PDF = "pdf"
    WORD = "docx"
    EXCEL = "xlsx"
    POWERPOINT = "pptx"
    HTML = "html"
    MARKDOWN = "md"
    TEXT = "txt"
    CSV = "csv"
    JSON = "json"
    IMAGE = "image"
    AUDIO = "audio"
    YOUTUBE = "youtube"
    EPUB = "epub"
    UNKNOWN = "unknown"
```

### `FormatDetector`

```python
FormatDetector.detect(path: str) -> DocFormat
```

Detect format from file extension; falls back to magic-byte inspection.

### `MarkdownNormalizer`

```python
MarkdownNormalizer(audit_callback=None)
MarkdownNormalizer.normalize(markdown: str, source_path="") -> dict
```

Extract headings, tables, links, code blocks; compute word/char counts; run audit callback.

## License

MIT License — see [LICENSE](LICENSE).
