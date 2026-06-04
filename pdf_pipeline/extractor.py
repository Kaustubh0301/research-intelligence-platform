"""
Stage 2 — PDF Text Extractor
=============================
Reads a PDF file with PyMuPDF, cleans the raw text, and returns
a RawExtraction dataclass ready for the section segmenter.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

EXTRACTOR_VERSION = "pymupdf-1.27"

# ── Cleaning patterns ──────────────────────────────────────────────────────────

# Common header/footer patterns in NeurIPS/ICML/ICLR papers
_HEADER_FOOTER = re.compile(
    r"^\s*(Preprint\.|Under review|NeurIPS\s+\d{4}|ICML\s+\d{4}|ICLR\s+\d{4}"
    r"|Published as a|Advances in Neural Information"
    r"|\d{1,4}\s*$)",
    re.IGNORECASE | re.MULTILINE,
)
# Unicode ligature normalization
_LIGATURES = str.maketrans({
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
    "ﬃ": "ffi", "ﬄ": "ffl", "ﬆ": "st",
})
# Collapse 3+ consecutive blank lines to 2
_EXCESS_BLANK = re.compile(r"\n{3,}")
# Lines that are purely page numbers or short artefacts
_LONE_PAGE_NUM = re.compile(r"^\s*\d{1,3}\s*$", re.MULTILINE)


@dataclass
class RawExtraction:
    paper_id:          str
    full_text:         str
    page_count:        int
    word_count:        int
    char_count:        int
    has_equations:     bool
    extractor_version: str
    extraction_ms:     int


def extract_text(paper_id: str, pdf_path: Path) -> RawExtraction:
    """
    Open a PDF file and return cleaned full text + metadata.
    Raises FileNotFoundError if the file is missing.
    Raises RuntimeError if PyMuPDF cannot open the file.
    """
    t0 = time.perf_counter()

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise RuntimeError(f"PyMuPDF could not open {pdf_path}: {exc}") from exc

    page_count = doc.page_count
    raw_pages: list[str] = []

    for page in doc:
        # sort=True fixes reading order in two-column layouts
        raw_pages.append(page.get_text(sort=True))

    doc.close()
    raw = "\n".join(raw_pages)

    # ── Apply cleaning pipeline ────────────────────────────────
    text = raw.translate(_LIGATURES)
    text = _LONE_PAGE_NUM.sub("", text)
    text = _HEADER_FOOTER.sub("", text)

    # Strip everything from "References\n" onward (removes bibliography noise)
    ref_match = re.search(r"\nReferences\s*\n", text, re.IGNORECASE)
    if ref_match:
        text = text[: ref_match.start()]

    text = _EXCESS_BLANK.sub("\n\n", text)
    text = text.strip()

    # ── Heuristics ────────────────────────────────────────────
    # Equation detection: more than 30 math-related unicode chars
    math_chars = sum(1 for c in text if "∀" <= c <= "⋿" or c in "∑∫∂∇×·")
    has_equations = math_chars > 30

    ms = int((time.perf_counter() - t0) * 1000)

    return RawExtraction(
        paper_id=paper_id,
        full_text=text,
        page_count=page_count,
        word_count=len(text.split()),
        char_count=len(text),
        has_equations=has_equations,
        extractor_version=EXTRACTOR_VERSION,
        extraction_ms=ms,
    )
