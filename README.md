> ⚠️ **Deprecated — legacy AIUCE family.** This repo is being consolidated into **SONUV** / **AIOBR** / a unified history archive (2026). No new work is accepted. Current status: **[aiuce.com](https://aiuce.com)**. _Marked 2026-07-15._
>
> _本仓库属旧 AIUCE 体系，正整合进 SONUV / AIOBR / 统一历史归档，不再接受新改动；最新状态见 aiuce.com。_
> **Disposition**: **Migrate → SONUV / AIOBR**
> **处置**：可验证接口/测试将整合进 SONUV 或 AIOBR（运行时/治理能力）；本仓不再作为独立产品维护，源码迁移待目标仓就绪。


# aiuce-document-ingestor

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Formats](https://img.shields.io/badge/Formats-PDF%20%7C%20DOCX%20%7C%20XLSX%20%7C%20PPTX%20%7C%20HTML-orange.svg)]()

**Universal document ingestion: convert any document to Markdown + structured JSON.**

## Features

- **Multi-format support** — PDF, Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), HTML, Markdown, plain text, CSV, images (OCR), EPUB
- **Dual-track output** — Markdown for humans, structured JSON for AI pipelines
- **Automatic format detection** — extension-based with magic-byte fallback
- **Markdown normalization** — extracts headings, tables, links, code blocks
- **Optional content audit** — plug in a custom callback to enforce content policy
- **Batch ingestion** — process multiple files with a progress callback

## Installation

```bash
# Core package
pip install aiuce-document-ingestor

# Recommended converter
pip install markitdown

# Optional: OCR support
# macOS
brew install tesseract tesseract-lang
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

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

| Format | Extension(s) | Converter |
|--------|-------------|-----------|
| PDF | `.pdf` | markitdown / pdftotext |
| Word | `.docx`, `.doc` | markitdown |
| Excel | `.xlsx`, `.xls` | markitdown |
| PowerPoint | `.pptx`, `.ppt` | markitdown |
| HTML | `.html`, `.htm` | pandoc / regex |
| Markdown | `.md` | direct read |
| Plain text | `.txt` | direct read |
| CSV | `.csv` | built-in CSV parser |
| Image | `.jpg`, `.jpeg`, `.png`, `.gif` | tesseract OCR |
| EPUB | `.epub` | markitdown |

## Batch Ingestion

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

## License

MIT License — see [LICENSE](LICENSE).
