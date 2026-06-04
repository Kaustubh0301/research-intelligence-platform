"""
Stage 3 — Section Segmenter  (regex-v3)
========================================
Splits cleaned full text into named sections using a three-pass strategy:

Pass 1 — explicit header regex
        Handles all four numbering styles:
          "Methodology"          bare
          "3 Methodology"        space-separated
          "3.1 Methodology"      subsection
          "3.1. Methodology"     subsection with trailing dot

Pass 2 — results-into-experiments merge
        If `results` was not detected as a standalone section, its content
        is pulled from the tail of the `experiments` block so the LLM still
        receives result text without requiring a separate header.

Pass 3 — positional fallbacks
        Abstract fallback  : first 600 words if no abstract header found.
        Conclusion fallback: last N words, but trimmed at the first
                             Ethics / Acknowledgements / Appendix / Funding
                             boundary to avoid appending boilerplate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SEGMENTER_VERSION = "regex-v3"

# ── 1. Canonical section vocabulary ───────────────────────────────────────────
# Key = internal field name  |  Value = regex fragment (case-insensitive)
CANONICAL: dict[str, str] = {
    "abstract":     r"abstract",
    "introduction": r"introduction",
    # "background" intentionally excluded: it is almost always a *subsection* of
    # Methodology, not a standalone Related Work section. Including it caused
    # the parent "Methodology" header to appear with zero body text.
    "related_work": r"related\s+work|literature\s+review|prior\s+work",
    "methodology":  (
        r"method(?:ology|s)?"
        r"|approach"
        r"|proposed\s+(?:method|model|framework|approach)"
        r"|technical\s+approach"
    ),
    "experiments":  (
        r"experiment(?:s|al\s+(?:setup|evaluation|results?|details?))?"
        r"|evaluation"
        r"|empirical\s+(?:study|evaluation|results?)"
        r"|(?:experimental\s+)?(?:setup|settings?|protocol)"
        r"|benchmarks?"
    ),
    "results":      (
        r"results?"
        r"|findings"
        r"|quantitative\s+(?:analysis|results?)"
        r"|performance\s+(?:analysis|evaluation)"
        r"|main\s+results?"
    ),
    "discussion":   r"discussion|analysis|(?:error|failure)\s+analysis",
    "conclusion":   r"conclusions?\s*(?:and\s+future\s+work)?|summary(?:\s+and\s+conclusions?)?",
    "limitations":  r"limitations?|failure\s+cases?|broader\s+impact|scope",
    "future_work":  r"future\s+(?:work|directions?)|open\s+(?:problems?|questions?)",
}

# ── 2. Header pattern (3 numbering variants + bare) ───────────────────────────
# Matches lines like:
#   "Methodology"          — bare
#   "3 Methodology"        — integer + space
#   "3.1 Methodology"      — subsection (one dot)
#   "3.1.2 Methodology"    — sub-subsection (two dots)
#   "3. Methodology"       — integer + dot + space
#   "3.1. Methodology"     — subsection + trailing dot + space
# The number prefix is entirely optional.
_NUM_PREFIX = r"(?:\d+(?:\.\d+)*\.?\s+)?"

_HEADER_PAT = re.compile(
    r"^[ \t]*{num}({secs})[ \t]*$".format(
        num=_NUM_PREFIX,
        secs="|".join(CANONICAL.values()),
    ),
    re.IGNORECASE | re.MULTILINE,
)

# ── 3. Conclusion-trimming stopwords ──────────────────────────────────────────
# The fallback conclusion is cut at the first line that starts with one of these.
_CONCLUSION_STOP = re.compile(
    r"^\s*(?:"
    r"(?:\d+\.?\s*)?(?:ethical\s+considerations?|ethics|broader\s+impact)"
    r"|(?:\d+\.?\s*)?acknowledgem?ents?"
    r"|(?:\d+\.?\s*)?(?:funding|disclosure\s+of\s+funding)"
    r"|(?:\d+\.?\s*)?appendix"
    r"|author\s+contributions?"
    r"|references?"
    r")\b",
    re.IGNORECASE | re.MULTILINE,
)

# Strip trailing boilerplate from a detected conclusion block.
# Pattern 1: newline-anchored  (standalone section header on its own line)
_CONCLUSION_TRAIL = re.compile(
    r"\n\s*(?:acknowledgem?ents?|author\s+contributions?|ethical|funding|appendix).*",
    re.IGNORECASE | re.DOTALL,
)
# Pattern 2: inline sentence-opener  e.g. "…throughout. Acknowledgements. AA…"
# Matches ". Acknowledgements" / ". Author contributions" after a sentence end.
_CONCLUSION_INLINE = re.compile(
    r"[.!?]\s+(?:acknowledgem?ents?|author\s+contributions?|ethical\s+considerations?"
    r"|funding|disclosure\s+of\s+funding|appendix)\b.*",
    re.IGNORECASE | re.DOTALL,
)

# ── 4. Results-split heuristic ────────────────────────────────────────────────
# When results are embedded in experiments, we split at the first occurrence of
# one of these patterns (they usually introduce the actual numbers table).
_RESULTS_SPLIT = re.compile(
    r"\n(?=\s*(?:"
    r"(?:table|figure|tab\.)\s*\d"          # "Table 1 shows …"
    r"|we\s+(?:report|present|show|observe)" # "We report that …"
    r"|(?:main\s+)?results?"                 # standalone "Results" paragraph
    r"|performance\s+(?:of|on)"
    r"|(?:our\s+)?(?:model|method|approach)\s+(?:achieves?|outperforms?|surpasses?)"
    r"))",
    re.IGNORECASE,
)


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class PaperSections:
    paper_id:          str
    abstract:          str | None = None
    introduction:      str | None = None
    related_work:      str | None = None
    methodology:       str | None = None
    experiments:       str | None = None
    results:           str | None = None
    discussion:        str | None = None
    conclusion:        str | None = None
    limitations:       str | None = None
    future_work:       str | None = None
    full_text:         str        = ""
    sections_found:    list[str]  = field(default_factory=list)
    word_count:        int        = 0
    segmenter_version: str        = SEGMENTER_VERSION


# ── Helpers ───────────────────────────────────────────────────────────────────

def _canonical_key(header_text: str) -> str:
    """Map a matched header string back to its canonical key."""
    h = header_text.lower().strip()
    # Strip any leading number prefix before matching
    h = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", h).strip()
    for key, pat in CANONICAL.items():
        if re.search(r"^(?:" + pat + r")$", h, re.IGNORECASE):
            return key
    return "other"


def _truncate(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "\n[truncated]"


def _trim_conclusion(text: str) -> str:
    """
    Remove Ethics / Acknowledgements / Appendix / Funding tails from
    both detected and fallback conclusion text.

    Three independent passes cover all common patterns:
      1. Newline-anchored standalone header  (most common)
      2. Inline sentence-opener  ("…throughout. Acknowledgements. AA…")
      3. Line-start stop-word pattern  (section headers within body text)
    Each pass keeps the prefix before the boilerplate.
    The shortest surviving prefix wins (most aggressive trim).
    """
    candidates = [text]

    m = _CONCLUSION_TRAIL.search(text)
    if m:
        candidates.append(text[: m.start()].strip())

    m = _CONCLUSION_INLINE.search(text)
    if m:
        # Keep the sentence-ending punctuation, drop everything after
        candidates.append(text[: m.start() + 1].strip())

    m = _CONCLUSION_STOP.search(text)
    if m:
        candidates.append(text[: m.start()].strip())

    # Pick the shortest non-empty result (most aggressively trimmed)
    result = min((c for c in candidates if len(c.split()) >= 20), key=len, default=text)
    return result


# ── Core segmenter ────────────────────────────────────────────────────────────

def segment(paper_id: str, full_text: str) -> PaperSections:
    """
    Split full_text into named sections. Never raises — always returns
    a best-effort PaperSections, even if no headers are detected.
    """
    ps = PaperSections(
        paper_id=paper_id,
        full_text=full_text,
        word_count=len(full_text.split()),
    )

    # ── Pass 1: detect explicit section headers ────────────────
    matches: list[tuple[int, int, str]] = []  # (line_start, line_end, canonical_key)

    for m in _HEADER_PAT.finditer(full_text):
        key = _canonical_key(m.group())
        if key == "other":
            continue
        # Keep only the first occurrence of each canonical key
        if not any(k == key for _, _, k in matches):
            matches.append((m.start(), m.end(), key))

    matches.sort(key=lambda x: x[0])

    # Slice text between consecutive headers
    for i, (start, end, key) in enumerate(matches):
        next_start = matches[i + 1][0] if i + 1 < len(matches) else len(full_text)
        section_text = full_text[end:next_start].strip()
        if section_text:
            # Clean conclusion boilerplate even from explicit matches
            if key == "conclusion":
                section_text = _trim_conclusion(section_text)
            setattr(ps, key, section_text)

    # Only report a key as "found" when it actually has body text.
    # A header with empty content (e.g. immediately followed by a subsection header)
    # is structurally present but useless for the LLM — omit it from the count.
    ps.sections_found = [k for _, _, k in matches if getattr(ps, k, None)]

    # ── Pass 2: results-into-experiments merge ─────────────────
    # If no standalone `results` section was found but `experiments` exists,
    # try to split the experiments block at a natural results boundary.
    if not ps.results and ps.experiments:
        splits = list(_RESULTS_SPLIT.finditer(ps.experiments))
        # Only split if the candidate boundary is past the first 30% of the block
        if splits:
            # Find the last split candidate that starts after 30% of the text
            cutoff = int(len(ps.experiments) * 0.30)
            candidates = [s for s in splits if s.start() >= cutoff]
            if candidates:
                split_pos  = candidates[0].start()
                exp_part   = ps.experiments[:split_pos].strip()
                res_part   = ps.experiments[split_pos:].strip()
                if exp_part and len(res_part.split()) >= 50:
                    ps.experiments = exp_part
                    ps.results     = res_part
                    ps.sections_found.append("results_from_experiments")

    # ── Pass 3: positional fallbacks ──────────────────────────
    if not ps.abstract and len(full_text) > 500:
        ps.abstract = _truncate(full_text, 600)
        if "abstract" not in ps.sections_found:
            ps.sections_found.insert(0, "abstract_fallback")

    if not ps.conclusion and full_text:
        words = full_text.split()
        if len(words) > 600:
            raw_tail = " ".join(words[-600:])
            trimmed  = _trim_conclusion(raw_tail)
            # Only use fallback if trimming left a meaningful amount
            if len(trimmed.split()) >= 40:
                ps.conclusion = trimmed
                ps.sections_found.append("conclusion_fallback")

    return ps


# ── LLM context builder ───────────────────────────────────────────────────────

def build_llm_context(ps: PaperSections, max_words: int = 4000) -> str:
    """
    Assemble the high-signal section subset for the LLM.
    Priority order ensures the most valuable sections fit first within max_words.
    """
    PRIORITY = [
        ("abstract",    800),
        ("methodology", 1200),
        ("experiments", 700),
        ("results",     800),
        ("conclusion",  400),
        ("limitations", 300),
        ("future_work", 200),
    ]
    parts: list[str] = []
    used  = 0

    for key, cap in PRIORITY:
        text = getattr(ps, key, None)
        if not text:
            continue
        budget = min(cap, max_words - used)
        if budget <= 50:
            break
        chunk = _truncate(text, budget)
        parts.append(f"=== {key.upper().replace('_', ' ')} ===\n{chunk}")
        used += len(chunk.split())

    return "\n\n".join(parts)


# ── Quality report ────────────────────────────────────────────────────────────

def quality_report(ps: PaperSections) -> dict:
    """Return a dict describing section detection quality for logging/reporting."""
    HIGH_VALUE = {"abstract", "methodology", "experiments", "results", "conclusion"}
    found_set  = set(ps.sections_found)
    # Normalise fallback tags for coverage calculation
    effective  = {s.replace("_fallback", "").replace("_from_experiments", "") for s in found_set}

    return {
        "sections_found":     ps.sections_found,
        "n_sections":         len(ps.sections_found),
        "high_value_found":   sorted(HIGH_VALUE & effective),
        "high_value_missing": sorted(HIGH_VALUE - effective),
        "coverage_pct":       round(len(HIGH_VALUE & effective) / len(HIGH_VALUE) * 100),
        "total_words":        ps.word_count,
        "methodology_words":  len((ps.methodology or "").split()),
        "experiments_words":  len((ps.experiments or "").split()),
        "results_words":      len((ps.results     or "").split()),
        "conclusion_words":   len((ps.conclusion  or "").split()),
    }
