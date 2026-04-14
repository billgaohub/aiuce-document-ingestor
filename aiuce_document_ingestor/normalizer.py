"""
AIUCE Document Ingestor — Markdown normalizer module
"""

import re
from typing import Any, Callable, Dict, Optional


class MarkdownNormalizer:
    """
    Normalize Markdown content:
    - Extract headings, tables, links, and code blocks
    - Compute word/char counts
    - Optionally run a content audit callback
    """

    def __init__(self, audit_callback: Optional[Callable[[str], Dict[str, Any]]] = None):
        """
        Args:
            audit_callback: Optional function(content: str) -> dict with keys
                            'passed' (bool) and 'reason' (str).
        """
        self._audit = audit_callback

    def normalize(self, markdown: str, source_path: str = "") -> Dict[str, Any]:
        """
        Normalize a Markdown string and extract structured metadata.

        Returns:
            dict with keys: markdown, headings, tables, links,
                            code_blocks, word_count, char_count,
                            passed, reason
        """
        result: Dict[str, Any] = {
            "markdown": markdown,
            "tables": [],
            "headings": [],
            "links": [],
            "code_blocks": [],
            "passed": True,
            "reason": "",
        }

        # ── Heading extraction ────────────────────────────────
        headings = re.findall(r"^(#{1,6})\s+(.+)$", markdown, re.MULTILINE)
        result["headings"] = [{"level": len(h), "text": t.strip()} for h, t in headings]

        # ── Table extraction ──────────────────────────────────
        # Simple Markdown tables: | col1 | col2 |
        table_blocks = re.findall(r"(\|.+\|(?:\n\|[-: |]+\|)?(?:\n\|.+\|)*)", markdown)
        for block in table_blocks:
            rows = [re.findall(r"\|([^\|]+)", row) for row in block.strip().split("\n")]
            if rows:
                result["tables"].append({
                    "rows": [[c.strip() for c in row] for row in rows]
                })

        # ── Link extraction ───────────────────────────────────
        links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", markdown)
        result["links"] = [{"text": t, "url": u} for t, u in links]

        # ── Code block extraction ─────────────────────────────
        code_blocks = re.findall(r"```(\w*)\n(.*?)```", markdown, re.DOTALL)
        result["code_blocks"] = [
            {"lang": lang, "code": code.strip()} for lang, code in code_blocks
        ]

        # ── Content audit ─────────────────────────────────────
        if self._audit:
            # Strip Markdown markup to get plain text for audit
            plain = re.sub(r"[#*`\[\]()>_~|-]", "", markdown)
            plain = re.sub(r"\n+", " ", plain).strip()[:2000]
            r = self._audit(plain)
            result["passed"] = bool(r.get("passed", True))
            result["reason"] = r.get("reason", "") if not result["passed"] else ""

        # ── Statistics ────────────────────────────────────────
        result["word_count"] = len(re.findall(r"[\w\u4e00-\u9fff]+", markdown))
        result["char_count"] = len(markdown)

        return result
