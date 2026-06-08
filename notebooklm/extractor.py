"""
NotebookLM response extractor.

Parses the structured text returned by query_notebook() into typed
Python objects. Every field is based on the validated format from
notebooklm/validate_prompts.py — do not change the field labels in the
query prompts without updating the constants here.

Observed format (validated June 2026, notebooklm-mcp-cli 0.7.0):

    PAPER: <exact title>
    FIELD: <value> | <value>        # pipe-separated multi-value
    FIELD: <value>                  # single value
    FIELD: <name> :: <task>         # key::value (datasets / findings)
    FIELD: NONE                     # explicit empty
    ===
    PAPER: ...

Structural guarantees confirmed by validation:
  - Blocks per query vary; every field label present per block
  - === always appears between blocks and after the last block
  - PAPER: is always the first line of a block
  - Citation refs [1, 2] appear inline only in the datasets query
  - Repeating-line fields (USE_CASE:, STRENGTH:, LIMITATION:, APPLICATION:,
    DIRECTION:, FINDING:) use one label per line, not pipe-separated

Analysis V2 (2026-06-08): 7 analysis prompt parsers added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Field label constants (must match the prompts in validate_prompts.py) ─────

LABEL_PAPER       = "PAPER:"
LABEL_SUMMARY     = "SUMMARY:"
LABEL_ADVANTAGE   = "ADVANTAGE:"    # V1 legacy label (still parsed for old synthesis rows)
LABEL_LIMITATION  = "LIMITATION:"
LABEL_FUTURE_WORK = "FUTURE_WORK:"  # V1 legacy label
LABEL_INTRODUCES  = "INTRODUCES:"
LABEL_USES        = "USES:"
LABEL_DATASET     = "DATASET:"
LABEL_CATEGORIES  = "CATEGORIES:"
LABEL_METHODOLOGY = "METHODOLOGY:"  # used in both categories prompt (short names) and methodology prompt (prose)
LABEL_USE_CASE    = "USE_CASE:"     # V1 legacy label

# Analysis V2 labels
LABEL_STRENGTH    = "STRENGTH:"
LABEL_FINDING     = "FINDING:"
LABEL_APPLICATION = "APPLICATION:"
LABEL_DIRECTION   = "DIRECTION:"

# Citation ref pattern: [1], [1, 2], [1-3] — always strip from field values
_CITE_RE = re.compile(r"\s*\[\d+(?:[,\s\-]\s*\d+)*\]")

# Block separator
_BLOCK_SEP = re.compile(r"\n===+\n?")

# Allowed category values (from the query prompt)
VALID_CATEGORIES = frozenset({
    "LLM", "Vision", "Multimodal", "Agentic-AI", "Safety", "Efficiency",
    "NLP", "RL", "Theory", "Graph", "Biomedical", "Robotics", "Code",
    "Retrieval", "Generative",
})


# ── Parsed result types ───────────────────────────────────────────────────────

@dataclass
class ParsedSummary:
    raw_title:   str
    paper_id:    Optional[str]    # resolved after title matching
    summary:     str
    advantages:  list[str]
    limitations: list[str]
    future_work: list[str]
    match_score: float = 0.0


@dataclass
class ParsedTechniques:
    raw_title:  str
    paper_id:   Optional[str]
    introduces: list[str]        # role='introduces'
    uses:       list[str]        # role='uses'
    match_score: float = 0.0


@dataclass
class ParsedDataset:
    name: str
    task: str                    # what it evaluates


@dataclass
class ParsedDatasets:
    raw_title:  str
    paper_id:   Optional[str]
    datasets:   list[ParsedDataset]
    match_score: float = 0.0


@dataclass
class ParsedCategories:
    raw_title:    str
    paper_id:     Optional[str]
    categories:   list[str]
    methodologies: list[str]
    match_score:  float = 0.0


@dataclass
class ParsedUseCases:
    raw_title:  str
    paper_id:   Optional[str]
    use_cases:  list[str]
    match_score: float = 0.0


# ── Analysis V2 parsed types ──────────────────────────────────────────────────

@dataclass
class ParsedMethodology:
    """Parsed result from the 'methodology' prompt — multi-paragraph prose."""
    raw_title:   str
    paper_id:    Optional[str]
    methodology: str             # multi-paragraph text blob
    match_score: float = 0.0


@dataclass
class ParsedFinding:
    """Single structured experimental result triple."""
    benchmark: str
    metric:    str
    scores:    str               # "X vs Y" string as returned


@dataclass
class ParsedExperimentalFindings:
    """Parsed result from the 'experimental_findings' prompt."""
    raw_title: str
    paper_id:  Optional[str]
    findings:  list[ParsedFinding]
    match_score: float = 0.0


@dataclass
class ParsedStrengths:
    """Parsed result from the 'strengths' prompt — repeated STRENGTH: lines."""
    raw_title:  str
    paper_id:   Optional[str]
    strengths:  list[str]
    match_score: float = 0.0


@dataclass
class ParsedLimitations:
    """Parsed result from the 'limitations' prompt — repeated LIMITATION: lines."""
    raw_title:   str
    paper_id:    Optional[str]
    limitations: list[str]
    match_score: float = 0.0


@dataclass
class ParsedPracticalApplications:
    """Parsed result from the 'practical_applications' prompt — repeated APPLICATION: lines."""
    raw_title:    str
    paper_id:     Optional[str]
    applications: list[str]
    match_score:  float = 0.0


@dataclass
class ParsedFutureResearchDirections:
    """Parsed result from the 'future_research_directions' prompt — repeated DIRECTION: lines."""
    raw_title:   str
    paper_id:    Optional[str]
    directions:  list[str]
    match_score: float = 0.0


@dataclass
class ExtractionResult:
    """All parsed output from one full set of prompts for a notebook."""
    # V1 metadata prompts (unchanged)
    summaries:   list[ParsedSummary]    = field(default_factory=list)
    techniques:  list[ParsedTechniques] = field(default_factory=list)
    datasets:    list[ParsedDatasets]   = field(default_factory=list)
    categories:  list[ParsedCategories] = field(default_factory=list)
    use_cases:   list[ParsedUseCases]   = field(default_factory=list)   # legacy
    # V2 analysis prompts
    methodologies:              list[ParsedMethodology]              = field(default_factory=list)
    experimental_findings:      list[ParsedExperimentalFindings]     = field(default_factory=list)
    strengths:                  list[ParsedStrengths]                = field(default_factory=list)
    limitations_v2:             list[ParsedLimitations]              = field(default_factory=list)
    practical_applications:     list[ParsedPracticalApplications]    = field(default_factory=list)
    future_research_directions: list[ParsedFutureResearchDirections] = field(default_factory=list)
    unmatched:                  list[str]                            = field(default_factory=list)


# ── Title matching ────────────────────────────────────────────────────────────

def _tokens(s: str) -> set[str]:
    """Same tokeniser as ingestion/enrich_citations.py."""
    return {w.lower().strip(".,:-()[]") for w in s.split() if len(w) > 2}


def match_title(
    raw_title: str,
    candidates: list[tuple[str, str]],  # [(paper_id, db_title), ...]
    threshold: float = 0.5,
) -> tuple[Optional[str], float]:
    """
    Return (paper_id, overlap_score) for the best match in candidates.
    Returns (None, 0.0) if no candidate clears the threshold.

    Threshold is 0.5 (lower than S2's 0.75) because NotebookLM occasionally
    truncates long titles slightly but never fully paraphrases them.
    """
    raw_tok = _tokens(raw_title)
    if not raw_tok:
        return None, 0.0

    best_id    = None
    best_score = 0.0
    for pid, db_title in candidates:
        db_tok = _tokens(db_title)
        if not db_tok:
            continue
        score = len(raw_tok & db_tok) / max(len(raw_tok), len(db_tok))
        if score > best_score:
            best_score = score
            best_id    = pid

    if best_score < threshold:
        return None, best_score
    return best_id, best_score


# ── Low-level text helpers ────────────────────────────────────────────────────

def _strip_citations(text: str) -> str:
    """Remove inline citation refs: [1], [1, 2], [1-3]."""
    return _CITE_RE.sub("", text).strip()


def _parse_pipe_list(value: str) -> list[str]:
    """
    Split a pipe-separated value string, strip citations and whitespace,
    and drop empty strings and literal 'NONE' items.
    """
    items = [_strip_citations(v).strip() for v in value.split("|")]
    return [v for v in items if v and v.upper() != "NONE"]


def _get_field(lines: list[str], label: str) -> str:
    """Return the value of the first line starting with label, or ''."""
    prefix = label + " "
    for ln in lines:
        if ln.startswith(prefix):
            return ln[len(prefix):].strip()
        if ln.strip() == label:
            return ""
    return ""


def _get_all_fields(lines: list[str], label: str) -> list[str]:
    """Return values for ALL lines starting with label (e.g. USE_CASE:)."""
    prefix = label + " "
    values = []
    for ln in lines:
        if ln.startswith(prefix):
            v = _strip_citations(ln[len(prefix):].strip())
            if v and v.upper() != "NONE":
                values.append(v)
    return values


def _split_blocks(answer: str) -> list[list[str]]:
    """
    Split the answer on === and return each block as a list of non-empty lines.
    Blocks that don't start with PAPER: are discarded.
    """
    raw_blocks = _BLOCK_SEP.split(answer)
    blocks = []
    for raw in raw_blocks:
        lines = [ln.rstrip() for ln in raw.strip().splitlines() if ln.strip()]
        if lines and lines[0].startswith(LABEL_PAPER):
            blocks.append(lines)
    return blocks


def _raw_title_from_block(lines: list[str]) -> str:
    """Extract the title from the PAPER: line."""
    first = lines[0]
    return first[len(LABEL_PAPER):].strip()


# ── Per-query parsers ─────────────────────────────────────────────────────────

def parse_summary(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedSummary]:
    results = []
    for lines in _split_blocks(answer):
        raw_title = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)

        summary    = _strip_citations(_get_field(lines, LABEL_SUMMARY))
        advantages = _parse_pipe_list(_get_field(lines, LABEL_ADVANTAGE))
        limitations = _parse_pipe_list(_get_field(lines, LABEL_LIMITATION))
        future_work = _parse_pipe_list(_get_field(lines, LABEL_FUTURE_WORK))

        results.append(ParsedSummary(
            raw_title   = raw_title,
            paper_id    = pid,
            summary     = summary,
            advantages  = advantages,
            limitations = limitations,
            future_work = future_work,
            match_score = score,
        ))
    return results


def parse_techniques(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedTechniques]:
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)

        introduces = _parse_pipe_list(_get_field(lines, LABEL_INTRODUCES))
        uses       = _parse_pipe_list(_get_field(lines, LABEL_USES))

        results.append(ParsedTechniques(
            raw_title   = raw_title,
            paper_id    = pid,
            introduces  = introduces,
            uses        = uses,
            match_score = score,
        ))
    return results


def parse_datasets(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedDatasets]:
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)

        datasets: list[ParsedDataset] = []
        for ln in lines[1:]:
            if not ln.startswith(LABEL_DATASET + " "):
                continue
            raw_val = _strip_citations(ln[len(LABEL_DATASET):].strip())
            if raw_val.upper() == "NONE" or not raw_val:
                continue
            if " :: " in raw_val:
                name, task = raw_val.split(" :: ", 1)
            else:
                name, task = raw_val, ""
            name = name.strip()
            task = task.strip()
            if name:
                datasets.append(ParsedDataset(name=name, task=task))

        results.append(ParsedDatasets(
            raw_title   = raw_title,
            paper_id    = pid,
            datasets    = datasets,
            match_score = score,
        ))
    return results


def parse_categories(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedCategories]:
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)

        raw_cats = _parse_pipe_list(_get_field(lines, LABEL_CATEGORIES))
        # Validate against the allowed list; keep unknowns with a warning tag
        categories   = [c for c in raw_cats if c in VALID_CATEGORIES]
        methodologies = _parse_pipe_list(_get_field(lines, LABEL_METHODOLOGY))

        results.append(ParsedCategories(
            raw_title     = raw_title,
            paper_id      = pid,
            categories    = categories,
            methodologies = methodologies,
            match_score   = score,
        ))
    return results


def parse_use_cases(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedUseCases]:
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)
        use_cases  = _get_all_fields(lines, LABEL_USE_CASE)

        results.append(ParsedUseCases(
            raw_title   = raw_title,
            paper_id    = pid,
            use_cases   = use_cases,
            match_score = score,
        ))
    return results


# ── Analysis V2 parsers ───────────────────────────────────────────────────────

def parse_methodology(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedMethodology]:
    """Parse 'methodology' prompt response — multi-paragraph prose per paper."""
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)

        # METHODOLOGY: value may span multiple lines; collect everything after
        # the METHODOLOGY: line up to the next recognised label or end of block.
        methodology_lines: list[str] = []
        in_methodology = False
        for ln in lines[1:]:
            if ln.startswith(LABEL_METHODOLOGY + " ") or ln.strip() == LABEL_METHODOLOGY:
                in_methodology = True
                val = ln[len(LABEL_METHODOLOGY):].strip()
                if val and val.upper() != "NONE":
                    methodology_lines.append(val)
            elif in_methodology and not any(
                ln.startswith(lbl) for lbl in (
                    LABEL_SUMMARY, LABEL_ADVANTAGE, LABEL_LIMITATION,
                    LABEL_FUTURE_WORK, LABEL_INTRODUCES, LABEL_USES,
                    LABEL_DATASET, LABEL_CATEGORIES, LABEL_USE_CASE,
                    LABEL_STRENGTH, LABEL_FINDING, LABEL_APPLICATION,
                    LABEL_DIRECTION, LABEL_PAPER,
                )
            ):
                # Continuation line of the methodology prose
                methodology_lines.append(ln)
            else:
                in_methodology = False

        methodology = _strip_citations(" ".join(methodology_lines)).strip()

        results.append(ParsedMethodology(
            raw_title   = raw_title,
            paper_id    = pid,
            methodology = methodology,
            match_score = score,
        ))
    return results


def parse_experimental_findings(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedExperimentalFindings]:
    """Parse 'experimental_findings' prompt response — FINDING: name :: metric :: scores."""
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)

        findings: list[ParsedFinding] = []
        for ln in lines[1:]:
            if not ln.startswith(LABEL_FINDING + " "):
                continue
            raw_val = _strip_citations(ln[len(LABEL_FINDING):].strip())
            if not raw_val or raw_val.upper() == "NONE":
                continue
            parts = raw_val.split(" :: ", 2)
            if len(parts) == 3:
                benchmark, metric, scores = parts
            elif len(parts) == 2:
                benchmark, metric = parts
                scores = ""
            else:
                benchmark, metric, scores = raw_val, "", ""
            findings.append(ParsedFinding(
                benchmark = benchmark.strip(),
                metric    = metric.strip(),
                scores    = scores.strip(),
            ))

        results.append(ParsedExperimentalFindings(
            raw_title   = raw_title,
            paper_id    = pid,
            findings    = findings,
            match_score = score,
        ))
    return results


def parse_strengths(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedStrengths]:
    """Parse 'strengths' prompt response — repeated STRENGTH: lines."""
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)
        strengths  = _get_all_fields(lines, LABEL_STRENGTH)

        results.append(ParsedStrengths(
            raw_title   = raw_title,
            paper_id    = pid,
            strengths   = strengths,
            match_score = score,
        ))
    return results


def parse_limitations_v2(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedLimitations]:
    """Parse 'limitations' prompt response — repeated LIMITATION: lines."""
    results = []
    for lines in _split_blocks(answer):
        raw_title   = _raw_title_from_block(lines)
        pid, score  = match_title(raw_title, candidates)
        limitations = _get_all_fields(lines, LABEL_LIMITATION)

        results.append(ParsedLimitations(
            raw_title   = raw_title,
            paper_id    = pid,
            limitations = limitations,
            match_score = score,
        ))
    return results


def parse_practical_applications(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedPracticalApplications]:
    """Parse 'practical_applications' prompt response — repeated APPLICATION: lines."""
    results = []
    for lines in _split_blocks(answer):
        raw_title    = _raw_title_from_block(lines)
        pid, score   = match_title(raw_title, candidates)
        applications = _get_all_fields(lines, LABEL_APPLICATION)

        results.append(ParsedPracticalApplications(
            raw_title    = raw_title,
            paper_id     = pid,
            applications = applications,
            match_score  = score,
        ))
    return results


def parse_future_research_directions(
    answer: str,
    candidates: list[tuple[str, str]],
) -> list[ParsedFutureResearchDirections]:
    """Parse 'future_research_directions' prompt response — repeated DIRECTION: lines."""
    results = []
    for lines in _split_blocks(answer):
        raw_title  = _raw_title_from_block(lines)
        pid, score = match_title(raw_title, candidates)
        directions = _get_all_fields(lines, LABEL_DIRECTION)

        results.append(ParsedFutureResearchDirections(
            raw_title   = raw_title,
            paper_id    = pid,
            directions  = directions,
            match_score = score,
        ))
    return results


# ── Unified entry point ───────────────────────────────────────────────────────

def extract_all(
    responses: dict[str, str],          # {query_name: answer_text}
    candidates: list[tuple[str, str]],  # [(paper_id, title), ...]
) -> ExtractionResult:
    """
    Parse all query responses into a single ExtractionResult.

    V1 metadata keys: 'summary', 'techniques', 'datasets', 'categories', 'use_cases'
    V2 analysis keys: 'methodology', 'experimental_findings', 'strengths',
                      'limitations', 'practical_applications',
                      'future_research_directions'
    """
    result = ExtractionResult()

    # V1 metadata parsers (unchanged)
    if "summary" in responses:
        result.summaries = parse_summary(responses["summary"], candidates)
    if "techniques" in responses:
        result.techniques = parse_techniques(responses["techniques"], candidates)
    if "datasets" in responses:
        result.datasets = parse_datasets(responses["datasets"], candidates)
    if "categories" in responses:
        result.categories = parse_categories(responses["categories"], candidates)
    if "use_cases" in responses:
        result.use_cases = parse_use_cases(responses["use_cases"], candidates)

    # V2 analysis parsers
    if "methodology" in responses:
        result.methodologies = parse_methodology(responses["methodology"], candidates)
    if "experimental_findings" in responses:
        result.experimental_findings = parse_experimental_findings(
            responses["experimental_findings"], candidates
        )
    if "strengths" in responses:
        result.strengths = parse_strengths(responses["strengths"], candidates)
    if "limitations" in responses:
        result.limitations_v2 = parse_limitations_v2(responses["limitations"], candidates)
    if "practical_applications" in responses:
        result.practical_applications = parse_practical_applications(
            responses["practical_applications"], candidates
        )
    if "future_research_directions" in responses:
        result.future_research_directions = parse_future_research_directions(
            responses["future_research_directions"], candidates
        )

    # Collect paper titles that could not be matched to a DB record
    all_parsed: list = (
        result.summaries + result.techniques +
        result.datasets  + result.categories +
        result.use_cases + result.methodologies +
        result.experimental_findings + result.strengths +
        result.limitations_v2 + result.practical_applications +
        result.future_research_directions
    )
    result.unmatched = sorted({
        p.raw_title for p in all_parsed if p.paper_id is None
    })

    return result
