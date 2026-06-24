"""
Claude-based paper analysis pipeline.

Replaces the NotebookLM Stage D+E pipeline for conferences where we want
faster, per-paper analysis using the Anthropic API.

Produces identical DB output to the NotebookLM pipeline:
  paper_analyses, paper_techniques, paper_datasets, paper_categories,
  paper_methodologies — all via the existing normalizer.

Usage:
    python -m corpus_intel.claude_analyze --conference ACL --year 2024
    python -m corpus_intel.claude_analyze --conference ACL --year 2024 --limit 50
    python -m corpus_intel.claude_analyze --conference ACL --year 2024 --force
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

from sqlalchemy import select

from db.session import get_session
from db.models import (
    Author, Conference, ConferenceEdition, Paper, PaperAnalysisRecord,
    PaperAuthor,
)
from llm.providers import get_provider
from notebooklm import extractor, normalizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

MODEL_LABEL = "claude/corpus_intel"

# Retry config
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # seconds

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a rigorous ML research analyst. Extract structured information "
    "from paper abstracts. Be precise and concise. Follow the format exactly."
)

_PROMPT_TEMPLATE = """\
Analyze this ML research paper and extract structured information.

PAPER: {title}
AUTHORS: {authors}
ABSTRACT: {abstract}

Provide your analysis in EXACTLY this format (use the exact field labels shown):

PAPER: {title}
SUMMARY: [3-5 paragraphs: (1) what problem this addresses and why it matters, \
(2) the core proposed approach at a conceptual level, (3) key results and how \
they compare to prior work, (4) the main contribution in one sentence. \
Target 200-400 words. Include specific technique names, dataset names, and \
quantitative claims where present in the abstract.]
METHODOLOGY: [2-3 paragraphs: (1) the technical approach — architecture, \
algorithm, or framework design, (2) key implementation decisions that distinguish \
it from prior work, (3) training or evaluation procedure if relevant. \
Target 100-200 words. Use precise technical terms. Focus on mechanism, not motivation.]
FINDING: [benchmark or dataset name] :: [metric name] :: [this paper's score vs baseline]
FINDING: [repeat for each key result — 2-5 findings. If no quantitative results, write: No quantitative benchmark evaluation]
STRENGTH: [1-2 sentences explaining WHY this aspect works mechanistically — 2-3 strengths]
STRENGTH: [next strength]
LIMITATION: [1-2 sentences: what the constraint is AND why it exists — 2-3 limitations]
LIMITATION: [next limitation]
APPLICATION: [2-3 sentences: specific deployment context, what the contribution enables, practical benefit vs current alternative — 2-3 applications]
APPLICATION: [next application]
DIRECTION: [1-2 sentences: open question or research opportunity this paper creates — 2-3 directions]
DIRECTION: [next direction]
INTRODUCES: [new method or model name] | [name]
USES: [existing method the paper builds on] | [name]
DATASET: [dataset name] :: [what task or metric it evaluates]
DATASET: [repeat for each dataset. If none, write: DATASET: NONE]
CATEGORIES: [tag] | [tag]
METHODOLOGY: [approach name] | [approach name]
===

Rules:
- CATEGORIES must come ONLY from: LLM | Vision | Multimodal | Agentic-AI | Safety | Efficiency | NLP | RL | Theory | Graph | Biomedical | Robotics | Code | Retrieval | Generative
- METHODOLOGY (last line) = short approach names e.g. "Fine-tuning | Contrastive Learning"
- INTRODUCES = novel contributions this paper presents (short names)
- USES = existing prior work methods the paper applies (short names)
- Do not add any text before or after the block
- End with ===
"""


def _build_prompt(paper: Paper, authors: list[str]) -> str:
    author_str = ", ".join(authors[:6]) if authors else "Unknown"
    abstract = (paper.abstract or "").strip() or "No abstract available."
    return _PROMPT_TEMPLATE.format(
        title=paper.title,
        authors=author_str,
        abstract=abstract,
    )


# ── Per-paper analysis ────────────────────────────────────────────────────────

def _analyze_paper(
    paper: Paper,
    authors: list[str],
    provider,
) -> str | None:
    prompt = _build_prompt(paper, authors)
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.generate_response(messages)
            return response
        except Exception as exc:
            log.warning("Claude call failed (attempt %d/%d) for %s: %s",
                        attempt, _MAX_RETRIES, paper.title[:50], exc)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY * attempt)
    return None


def _parse_response(response: str, paper: Paper) -> normalizer.NormalizationStats | None:
    """Parse Claude response using existing extractor, write via normalizer."""
    candidates = [(paper.id, paper.title)]

    # Build a fake ExtractionResult with all fields populated from one response
    result = extractor.ExtractionResult()

    summaries = extractor.parse_summary(response, candidates)
    if summaries and summaries[0].paper_id:
        result.summaries = summaries

    methodologies = extractor.parse_methodology(response, candidates)
    if methodologies and methodologies[0].paper_id:
        result.methodologies = methodologies

    findings = extractor.parse_experimental_findings(response, candidates)
    if findings and findings[0].paper_id:
        result.experimental_findings = findings

    strengths = extractor.parse_strengths(response, candidates)
    if strengths and strengths[0].paper_id:
        result.strengths = strengths

    limitations = extractor.parse_limitations_v2(response, candidates)
    if limitations and limitations[0].paper_id:
        result.limitations_v2 = limitations

    applications = extractor.parse_practical_applications(response, candidates)
    if applications and applications[0].paper_id:
        result.practical_applications = applications

    directions = extractor.parse_future_research_directions(response, candidates)
    if directions and directions[0].paper_id:
        result.future_research_directions = directions

    techniques = extractor.parse_techniques(response, candidates)
    if techniques and techniques[0].paper_id:
        result.techniques = techniques

    datasets = extractor.parse_datasets(response, candidates)
    if datasets and datasets[0].paper_id:
        result.datasets = datasets

    categories = extractor.parse_categories(response, candidates)
    if categories and categories[0].paper_id:
        result.categories = categories

    if not any([result.summaries, result.techniques, result.datasets, result.categories]):
        log.warning("No fields parsed for paper %s — response may be malformed", paper.title[:50])
        return None

    return result


def _write_result(
    session,
    result: extractor.ExtractionResult,
    notebook_id: str = "claude-direct",
) -> normalizer.NormalizationStats:
    stats = normalizer.normalize(
        session=session,
        result=result,
        notebook_id=notebook_id,
        synthesis_ids={},
    )
    # Override model label so we can distinguish Claude vs NotebookLM rows
    rec = session.scalar(
        select(PaperAnalysisRecord).where(
            PaperAnalysisRecord.paper_id.in_(
                [s.paper_id for s in result.summaries if s.paper_id]
            )
        )
    )
    if rec:
        rec.model = MODEL_LABEL
    return stats


# ── Main runner ───────────────────────────────────────────────────────────────

def run(
    conference: str,
    year: int,
    limit: int = 500,
    force: bool = False,
) -> None:
    provider = get_provider(system_prompt=_SYSTEM)

    with get_session() as session:
        # Resolve conference + edition
        conf_row = session.scalar(
            select(Conference).where(Conference.short_name == conference.upper())
        )
        if not conf_row:
            log.error("Conference %s not found in DB — run ingestion first", conference)
            sys.exit(1)

        edition = session.scalar(
            select(ConferenceEdition).where(
                ConferenceEdition.conference_id == conf_row.id,
                ConferenceEdition.year == year,
            )
        )
        if not edition:
            log.error("%s %d not found in DB — run ingestion first", conference, year)
            sys.exit(1)

        # Get papers to analyze
        q = select(Paper).where(Paper.conference_edition_id == edition.id)
        if not force:
            # Skip papers that already have analysis
            analyzed_ids = session.scalars(select(PaperAnalysisRecord.paper_id)).all()
            q = q.where(Paper.id.notin_(analyzed_ids))
        q = q.limit(limit)

        papers = session.scalars(q).all()
        log.info("Analyzing %d %s %d papers with Claude", len(papers), conference, year)

        if not papers:
            log.info("No papers to analyze — all done or use --force to re-run")
            return

        # Pre-fetch authors for all papers
        author_map: dict[str, list[str]] = {}
        for paper in papers:
            rows = session.execute(
                select(Author.full_name)
                .join(PaperAuthor, PaperAuthor.author_id == Author.id)
                .where(PaperAuthor.paper_id == paper.id)
                .order_by(PaperAuthor.position)
                .limit(6)
            ).scalars().all()
            author_map[paper.id] = list(rows)

        # Process each paper
        total = len(papers)
        done = errors = skipped = 0

        for i, paper in enumerate(papers, 1):
            log.info("[%d/%d] %s", i, total, paper.title[:70])

            response = _analyze_paper(paper, author_map.get(paper.id, []), provider)
            if response is None:
                log.error("  → Claude call failed after %d retries, skipping", _MAX_RETRIES)
                errors += 1
                continue

            result = _parse_response(response, paper)
            if result is None:
                log.warning("  → Parse failed, skipping")
                skipped += 1
                continue

            stats = _write_result(session, result)
            session.commit()
            done += 1
            log.info(
                "  → analyses=%d techniques=%d datasets=%d categories=%d",
                stats.analyses_written, stats.techniques_written,
                stats.datasets_written, stats.categories_written,
            )

            # Brief pause to avoid hammering the API
            if i % 10 == 0:
                time.sleep(1)

    log.info("Done. analyzed=%d errors=%d skipped=%d", done, errors, skipped)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze papers with Claude API")
    parser.add_argument("--conference", "-c", required=True, help="Conference short name, e.g. ACL")
    parser.add_argument("--year",       "-y", type=int, required=True, help="Edition year, e.g. 2024")
    parser.add_argument("--limit",      "-n", type=int, default=500, help="Max papers to analyze")
    parser.add_argument("--force",      action="store_true", help="Re-analyze already-analyzed papers")
    args = parser.parse_args()

    run(
        conference=args.conference,
        year=args.year,
        limit=args.limit,
        force=args.force,
    )


if __name__ == "__main__":
    main()
