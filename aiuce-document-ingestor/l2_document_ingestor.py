"""
L2 感知层：Document Ingestor
Document Ingestor — 御史大夫/六扇门

融合来源：
- markitdown (microsoft/markitdown): 万物转 Markdown（PDF/Word/Excel/PPT/图片OCR）

核心职责：
1. 统一格式转换：所有文档 → Markdown
2. 双轨输出：JSON（AI消费） + Markdown（人消费）
3. 合宪性审查：文档内容过 L0 SovereigntyGateway
4. 结构保留：标题层级/表格/列表/链接/代码块
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
import os
import json
import tempfile
import subprocess
import logging
from pathlib import Path
from dataclasses import asdict

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 支持的格式（来自 markitdown）
# ═══════════════════════════════════════════════════════════════════

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
    IMAGE = "image"     # OCR
    AUDIO = "audio"     # 语音转录
    YOUTUBE = "youtube" # 油管字幕
    EPUB = "epub"
    UNKNOWN = "unknown"


@dataclass
class IngestResult:
    """文档摄取结果"""
    format: DocFormat
    file_path: str
    markdown_content: str
    structured_json: Dict[str, Any]   # AI消费：结构化 JSON
    word_count: int
    char_count: int
    tables: List[Dict[str, Any]] = field(default_factory=list)  # 提取的表格
    headings: List[str] = field(default_factory=list)            # 标题层级
    images: List[str] = field(default_factory=list)              # 图片路径
    links: List[str] = field(default_factory=list)               # 外部链接
    source_url: Optional[str] = None
    ingested_at: str = field(default_factory=datetime.now().isoformat)
    constitutional_passed: bool = True  # L0 合宪性审查结果
    constitutional_reason: str = ""     # 否决原因

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# Format Detector
# ═══════════════════════════════════════════════════════════════════

class FormatDetector:
    """
    格式检测（改造自 markitdown 格式支持列表）
    基于文件扩展名 + Magic bytes 检测
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
        b"PK\x03\x04": DocFormat.WORD,  # docx/xlsx/pptx 均为 ZIP
        b"<!DOCTYPE": DocFormat.HTML,
        b"<html": DocFormat.HTML,
    }

    @classmethod
    def detect(cls, path: str) -> DocFormat:
        """检测文件格式"""
        ext = Path(path).suffix.lower()
        if ext in cls.FORMAT_MAP:
            return cls.FORMAT_MAP[ext]

        # Magic bytes 检测
        try:
            with open(path, "rb") as f:
                header = f.read(16)
            for magic, fmt in cls.MAGIC_BYTES.items():
                if header.startswith(magic):
                    return fmt
        except Exception:
            pass

        return DocFormat.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
# Markdown Normalizer
# ═══════════════════════════════════════════════════════════════════

class MarkdownNormalizer:
    """
    Markdown 规范化（AIUCE 特有）
    - 标题层级展平（PDF → Markdown 时可能有异常层级）
    - 表格清理（去除多余空格/边框）
    - 链接提取（提取 href）
    - 代码块语言标注
    - 合宪性审查：内容过 L0 SovereigntyGateway
    """

    def __init__(self, sovereignty_gateway=None):
        self.sg = sovereignty_gateway

    def normalize(self, markdown: str, source_path: str = "") -> Dict[str, Any]:
        """规范化 Markdown，返回结构化 JSON"""
        result = {
            "markdown": markdown,
            "tables": [],
            "headings": [],
            "links": [],
            "code_blocks": [],
            "constitutional_passed": True,
            "constitutional_reason": "",
        }

        # ── 标题提取 ─────────────────────────────────────────
        headings = re.findall(r'^(#{1,6})\s+(.+)$', markdown, re.MULTILINE)
        result["headings"] = [{"level": len(h), "text": t.strip()} for h, t in headings]

        # ── 表格提取 ─────────────────────────────────────────
        # 简单表格：| col1 | col2 |
        table_blocks = re.findall(r'(\|.+\|(?:\n\|[-: |]+\|)?(?:\n\|.+\|)*)', markdown)
        for block in table_blocks:
            rows = [re.findall(r'\|([^\|]+)', row) for row in block.strip().split("\n")]
            if rows:
                result["tables"].append({"rows": [[c.strip() for c in row] for row in rows]})

        # ── 链接提取 ─────────────────────────────────────────
        links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', markdown)
        result["links"] = [{"text": t, "url": u} for t, u in links]

        # ── 代码块提取 ───────────────────────────────────────
        code_blocks = re.findall(r'```(\w*)\n(.*?)```', markdown, re.DOTALL)
        result["code_blocks"] = [{"lang": lang, "code": code.strip()} for lang, code in code_blocks]

        # ── 合宪性审查 ───────────────────────────────────────
        if self.sg:
            # 提取纯文本用于审查（去掉 Markdown 标记）
            plain_text = re.sub(r'[#*`\[\]()>_~|-]', '', markdown)
            plain_text = re.sub(r'\n+', ' ', plain_text).strip()[:2000]
            r = self.sg.audit(plain_text)
            result["constitutional_passed"] = not r.vetoed
            result["constitutional_reason"] = r.reason if r.vetoed else ""

        # ── 统计数据 ─────────────────────────────────────────
        result["word_count"] = len(re.findall(r'[\w\u4e00-\u9fff]+', markdown))
        result["char_count"] = len(markdown)

        return result


# ═══════════════════════════════════════════════════════════════════
# Document Ingestor（改造自 markitdown 核心逻辑）
# ═══════════════════════════════════════════════════════════════════

class DocumentIngestor:
    """
    文档摄取器（改造自 markitdown）

    AIUCE 改造要点：
    - markitdown: `DocumentConverter` → AIUCE: `DocumentIngestor`
    - markitdown: 直接输出 Markdown → AIUCE: 双轨输出（JSON + Markdown）
    - markitdown: CLI → AIUCE: Python API + SDK 封装
    - AIUCE 特有：L0 合宪性审查（L0 SovereigntyGateway）
    - AIUCE 特有：Markdown 规范化（标题/表格/链接提取）
    - AIUCE 特有：与 L3 CognitiveOrchestrator 联动

    使用方式：
        ingestor = DocumentIngestor()
        result = ingestor.ingest("/path/to/document.pdf")
        print(result.markdown_content)  # 人消费
        print(result.structured_json)   # AI消费
    """

    def __init__(self, sovereignty_gateway=None, use_llm_ocr: bool = False):
        self.format_detector = FormatDetector()
        self.normalizer = MarkdownNormalizer(sovereignty_gateway=sovereignty_gateway)
        self.use_llm_ocr = use_llm_ocr  # markitdown 支持 LLM OCR（需 API key）

    def ingest(
        self,
        path_or_url: str,
        source_url: Optional[str] = None,
        max_tables: int = 50,
    ) -> IngestResult:
        """
        统一摄取接口：文件路径/URL → IngestResult

        Args:
            path_or_url: 文件路径或 URL
            source_url: 原始 URL（用于网页剪藏）
            max_tables: 最大提取表格数
        """
        path = path_or_url

        # ── URL 模式 ────────────────────────────────────────
        if path.startswith("http://") or path.startswith("https://"):
            source_url = path
            path = self._download_url(path)

        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        fmt = self.format_detector.detect(path)
        logger.info(f"Ingesting {path} (format: {fmt.value})")

        # ── 格式转换 ────────────────────────────────────────
        if fmt == DocFormat.MARKDOWN:
            raw_markdown = Path(path).read_text(encoding="utf-8")
        elif fmt == DocFormat.TEXT:
            raw_markdown = self._text_to_markdown(path)
        elif fmt == DocFormat.PDF:
            raw_markdown = self._convert_pdf(path, use_llm=self.use_llm_ocr)
        elif fmt in (DocFormat.WORD, DocFormat.EXCEL, DocFormat.POWERPOINT):
            raw_markdown = self._convert_office(path)
        elif fmt == DocFormat.HTML:
            raw_markdown = self._html_to_markdown(path)
        elif fmt == DocFormat.IMAGE:
            raw_markdown = self._ocr_image(path, use_llm=self.use_llm_ocr)
        elif fmt == DocFormat.CSV:
            raw_markdown = self._csv_to_markdown(path)
        else:
            raw_markdown = f"# Document\n\n[Unsupported format: {fmt.value}]"

        # ── 规范化 ──────────────────────────────────────────
        normalized = self.normalizer.normalize(raw_markdown, path)

        # ── 双轨输出 ────────────────────────────────────────
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
            images=[],  # markitdown 不直接提取图片
            source_url=source_url,
            ingested_at=datetime.now().isoformat(),
            constitutional_passed=normalized["constitutional_passed"],
            constitutional_reason=normalized["constitutional_reason"],
        )

    def ingest_batch(
        self,
        paths: List[str],
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[IngestResult]:
        """批量摄取"""
        results = []
        for i, path in enumerate(paths):
            try:
                result = self.ingest(path)
                results.append(result)
                if on_progress:
                    on_progress(path, i + 1, len(paths))
            except Exception as e:
                logger.error(f"Failed to ingest {path}: {e}")
                results.append(IngestResult(
                    format=DocFormat.UNKNOWN,
                    file_path=path,
                    markdown_content="",
                    structured_json={"error": str(e)},
                    word_count=0,
                    char_count=0,
                ))
        return results

    # ── 格式转换实现（使用 markitdown CLI 或替代方案）───────

    def _has_markitdown(self) -> bool:
        """检查 markitdown 是否安装"""
        result = subprocess.run(["markitdown", "--version"],
                              capture_output=True, text=True)
        return result.returncode == 0

    def _convert_pdf(self, path: str, use_llm: bool = False) -> str:
        """PDF → Markdown（使用 markitdown 或 pdftotext）"""
        if self._has_markitdown():
            try:
                result = subprocess.run(
                    ["markitdown", path],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception as e:
                logger.warning(f"markitdown failed: {e}, falling back")

        # 降级方案：pdftotext
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", path, "-"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return self._plaintext_to_markdown(result.stdout)
        except Exception:
            pass

        return f"# PDF Document\n\n[Failed to extract text from PDF: {path}]"

    def _convert_office(self, path: str) -> str:
        """Office 文档 → Markdown（使用 markitdown）"""
        if self._has_markitdown():
            try:
                result = subprocess.run(
                    ["markitdown", path],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    return result.stdout
            except Exception as e:
                logger.warning(f"markitdown failed: {e}")

        return f"# Office Document\n\n[markitdown not installed: {path}]"

    def _html_to_markdown(self, path: str) -> str:
        """HTML → Markdown（使用 pandoc 或正则）"""
        try:
            result = subprocess.run(
                ["pandoc", "-f", "html", "-t", "markdown", path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass

        # 降级：正则提取文本
        try:
            html = Path(path).read_text(encoding="utf-8")
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return f"# Web Page\n\n{text}"
        except Exception:
            return f"# HTML Document\n\n[Failed to parse: {path}]"

    def _text_to_markdown(self, path: str) -> str:
        """纯文本 → Markdown"""
        text = Path(path).read_text(encoding="utf-8")
        return f"# Document\n\n{text}"

    def _plaintext_to_markdown(self, text: str) -> str:
        """纯文本 → Markdown（保留段落）"""
        paragraphs = re.split(r'\n{2,}', text)
        md_lines = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 已经是 Markdown 标题则保留
            if para.startswith('#'):
                md_lines.append(para)
            else:
                md_lines.append(para)
        return "\n\n".join(md_lines)

    def _csv_to_markdown(self, path: str) -> str:
        """CSV → Markdown 表格"""
        try:
            import csv
            with open(path, encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
            if not rows:
                return "# CSV\n\n[Empty]"
            header = rows[0]
            md = "| " + " | ".join(header) + " |\n"
            md += "| " + " | ".join(["---"] * len(header)) + " |\n"
            for row in rows[1:]:
                md += "| " + " | ".join(row[:len(header)]) + " |\n"
            return f"# CSV: {Path(path).name}\n\n{md}"
        except Exception as e:
            return f"# CSV\n\n[Failed to parse: {e}]"

    def _ocr_image(self, path: str, use_llm: bool = False) -> str:
        """图片 → Markdown（OCR）"""
        if use_llm:
            # markitdown LLM OCR（需要 API key）
            return "[LLM OCR requires OPENAI_API_KEY or ANTHROPIC_API_KEY]"
        try:
            result = subprocess.run(
                ["tesseract", path, "stdout", "-l", "chi_sim+eng"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return f"# Image OCR\n\n{result.stdout}"
        except Exception:
            pass
        return f"# Image\n\n[OCR not available: {path}]"

    def _download_url(self, url: str) -> str:
        """下载 URL 到临时文件"""
        try:
            import urllib.request
            tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
            urllib.request.urlretrieve(url, tmp.name)
            return tmp.name
        except Exception as e:
            raise RuntimeError(f"Failed to download {url}: {e}")
