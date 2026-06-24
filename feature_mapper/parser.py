"""
feature_mapper/parser.py
────────────────────────
Markdown / plain-text → structured sections.

Deterministic, dependency-free (stdlib re only). The LLM is applied to the
*meaning* of clean section text downstream — never to raw bytes — so this
stage strips code fences and Markdown chrome before the extractor sees it.

Public API:
    parse(text)         → list[RawSection]
    extract_title(text) → str | None
"""

from __future__ import annotations

import re

from feature_mapper.models import RawSection

# A Markdown heading line: 1–3 leading '#' then text.
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$", re.MULTILINE)

# Fenced code blocks (``` or ~~~), non-greedy across lines.
_CODE_FENCE_RE = re.compile(r"(```|~~~).*?(\1)", re.DOTALL)

# Lines that are pure Markdown chrome with no prose value.
_HR_RE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")          # --- *** ___
_IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")  # ![alt](url)
_BADGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")              # inline badges

# Minimum words for a section to be worth analysing.
_MIN_SECTION_WORDS = 15


def _strip_chrome(text: str) -> str:
    """Remove code fences, horizontal rules, image/badge lines, and HTML comments."""
    text = _CODE_FENCE_RE.sub(" ", text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    kept: list[str] = []
    for line in text.splitlines():
        if _HR_RE.match(line):
            continue
        if _IMAGE_LINE_RE.match(line):
            continue
        line = _BADGE_RE.sub("", line)
        kept.append(line)
    return "\n".join(kept).strip()


def _word_count(text: str) -> int:
    return len(text.split())


def extract_title(text: str) -> str | None:
    """Return the text of the first H1 heading, or None."""
    for m in _HEADING_RE.finditer(text):
        if len(m.group(1)) == 1:
            return m.group(2).strip()
    return None


def parse(text: str) -> list[RawSection]:
    """
    Split a document into heading-delimited sections.

    Text before the first heading becomes a section with heading=None.
    Code fences and Markdown chrome are stripped from each section's text.
    Sections shorter than _MIN_SECTION_WORDS (after stripping) are dropped.
    If no headings are present, the whole document is one section.
    """
    if not text or not text.strip():
        return []

    headings = list(_HEADING_RE.finditer(text))

    if not headings:
        body = _strip_chrome(text)
        if _word_count(body) >= _MIN_SECTION_WORDS:
            return [RawSection(heading=None, text=body)]
        # Even a short single block is worth returning rather than nothing.
        return [RawSection(heading=None, text=body)] if body else []

    sections: list[RawSection] = []

    # Preamble before the first heading.
    preamble = text[: headings[0].start()]
    pre_body = _strip_chrome(preamble)
    if _word_count(pre_body) >= _MIN_SECTION_WORDS:
        sections.append(RawSection(heading=None, text=pre_body))

    # Each heading + the body up to the next heading.
    for i, m in enumerate(headings):
        heading = m.group(2).strip()
        body_start = m.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = _strip_chrome(text[body_start:body_end])

        if _word_count(body) < _MIN_SECTION_WORDS:
            continue
        sections.append(RawSection(heading=heading, text=body))

    return sections


# ── Manual smoke test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = """# My RAG System
A retrieval-augmented generation system for enterprise search.

![build](https://img.shields.io/badge/build-passing-green)

## Dense Retrieval
We implement bi-encoder dense retrieval using DPR. Documents are indexed into
FAISS using all-MiniLM-L6-v2 embeddings. At query time the query is encoded and
ANN search retrieves the top-k candidates via inner product.

```python
index = faiss.IndexFlatIP(384)  # this code block should be stripped
```

## Setup
pip install foo

## Re-ranking
Retrieved candidates are re-ranked using a cross-encoder fine-tuned on MS MARCO.
The cross-encoder jointly encodes the query and each passage to produce a score.
"""
    print("TITLE:", extract_title(sample))
    for s in parse(sample):
        print(f"\n── heading={s.heading!r} ({_word_count(s.text)} words)")
        print(s.text)
