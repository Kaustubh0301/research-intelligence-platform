"""
Corpus Intelligence — Emerging Techniques

Classifies every canonical technique by adoption stage:

  EMERGING     — introduced in ≥1 paper AND adopted (used) by ≥1 *different* paper
  NOVEL        — introduced in ≥1 paper, not yet adopted by others
  ESTABLISHED  — used in ≥1 paper, never introduced in this corpus
  FOUNDATIONAL — Established + GENERIC IDF tier (ubiquitous baseline method)
  REFERENCED   — only appears as a comparison target or critique subject

Outputs:
  outputs/corpus_intel/emerging_techniques.csv
  outputs/corpus_intel/emerging_summary.md

Read-only. No DB writes. No schema changes.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python -m corpus_intel.emerging
"""

from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from corpus_intel._queries import (
    TIER_GENERIC,
    RoleAggregation,
    corpus_size,
    idf_tier,
    paper_titles,
    role_aggregation,
)

# ── Output paths ──────────────────────────────────────────────────────────────

_OUT_DIR = Path("outputs/corpus_intel")
CSV_PATH = _OUT_DIR / "emerging_techniques.csv"
MD_PATH  = _OUT_DIR / "emerging_summary.md"

# ── Stage labels ──────────────────────────────────────────────────────────────

STAGE_EMERGING     = "Emerging"
STAGE_NOVEL        = "Novel"
STAGE_ESTABLISHED  = "Established"
STAGE_FOUNDATIONAL = "Foundational"
STAGE_REFERENCED   = "Referenced"

# Canonical display order — highest signal value first
STAGE_ORDER = [
    STAGE_EMERGING,
    STAGE_NOVEL,
    STAGE_ESTABLISHED,
    STAGE_FOUNDATIONAL,
    STAGE_REFERENCED,
]


# ── Per-technique record ──────────────────────────────────────────────────────

@dataclass
class TechniqueRecord:
    canonical_name:      str
    stage:               str
    introduces_count:    int
    uses_count:          int
    cross_adoption_count: int   # uses by a paper other than the introducing paper
    compares_count:      int
    critiques_count:     int
    total_papers:        int
    idf_score:           float
    idf_tier:            str
    adoption_ratio:      float
    introducing_paper_ids: list[str]  # for markdown explanations
    using_paper_ids:       list[str]


# ── Stage classification ──────────────────────────────────────────────────────

def classify_stage(agg: RoleAggregation, tier: str) -> str:
    """
    Assign an adoption stage to a technique.

    EMERGING requires cross_adoption_count > 0 — at least one paper uses
    the technique that is NOT the paper that introduced it.  This prevents
    a single paper that both introduces and uses the same canonical technique
    (possible via normalization) from being falsely classified as Emerging.

    FOUNDATIONAL is checked before ESTABLISHED because it is a strict subset.
    """
    has_introduces    = agg.introduces_count > 0
    has_cross_adopted = agg.cross_adoption_count > 0

    if has_introduces and has_cross_adopted:
        return STAGE_EMERGING
    if has_introduces:
        return STAGE_NOVEL
    if agg.uses_count > 0:
        return STAGE_FOUNDATIONAL if tier == TIER_GENERIC else STAGE_ESTABLISHED
    return STAGE_REFERENCED


# ── Core analysis ─────────────────────────────────────────────────────────────

def run(conn) -> tuple[list[TechniqueRecord], int]:
    """
    Classify all canonical techniques by adoption stage.

    Returns (records, corpus_size).  Records are sorted by stage order
    (STAGE_ORDER) then by total_papers descending, then name ascending.
    """
    n_papers = corpus_size(conn)
    agg_map  = role_aggregation(conn)

    records: list[TechniqueRecord] = []

    for canon, agg in agg_map.items():
        score, tier = idf_tier(agg.total_papers, n_papers)
        stage       = classify_stage(agg, tier)

        records.append(TechniqueRecord(
            canonical_name        = canon,
            stage                 = stage,
            introduces_count      = agg.introduces_count,
            uses_count            = agg.uses_count,
            cross_adoption_count  = agg.cross_adoption_count,
            compares_count        = agg.compares_count,
            critiques_count       = agg.critiques_count,
            total_papers          = agg.total_papers,
            idf_score             = score,
            idf_tier              = tier,
            adoption_ratio        = agg.adoption_ratio,
            introducing_paper_ids = sorted(agg.introducing_papers),
            using_paper_ids       = sorted(agg.using_papers),
        ))

    stage_rank = {s: i for i, s in enumerate(STAGE_ORDER)}
    records.sort(
        key=lambda r: (stage_rank.get(r.stage, 99), -r.total_papers, r.canonical_name)
    )

    return records, n_papers


# ── CSV output ────────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "canonical_name",
    "stage",
    "introduces_count",
    "uses_count",
    "cross_adoption_count",
    "compares_count",
    "critiques_count",
    "total_papers",
    "idf_score",
    "idf_tier",
    "adoption_ratio",
]


def write_csv(records: list[TechniqueRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "canonical_name":      r.canonical_name,
                "stage":               r.stage,
                "introduces_count":    r.introduces_count,
                "uses_count":          r.uses_count,
                "cross_adoption_count": r.cross_adoption_count,
                "compares_count":      r.compares_count,
                "critiques_count":     r.critiques_count,
                "total_papers":        r.total_papers,
                "idf_score":           r.idf_score,
                "idf_tier":            r.idf_tier,
                "adoption_ratio":      r.adoption_ratio,
            })


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _shorten(s: str, max_len: int = 65) -> str:
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def _stage_distribution_table(records: list[TechniqueRecord]) -> str:
    counts = Counter(r.stage for r in records)
    total  = len(records)
    lines  = ["| Stage | Count | % of techniques |", "|---|---:|---:|"]
    for stage in STAGE_ORDER:
        n   = counts.get(stage, 0)
        pct = 100 * n / total if total else 0.0
        lines.append(f"| {stage} | {n} | {pct:.1f}% |")
    lines.append(f"| **Total** | **{total}** | 100% |")
    return "\n".join(lines)


def _emerging_table(records: list[TechniqueRecord], titles: dict[str, str]) -> str:
    rows = sorted(
        [r for r in records if r.stage == STAGE_EMERGING],
        key=lambda r: (-r.cross_adoption_count, -r.introduces_count, r.canonical_name),
    )
    if not rows:
        return "_No Emerging techniques at current corpus size._"

    lines = [
        "| Technique | Introduced by | Adopted by | Adoption ratio | IDF tier |",
        "|---|---:|---:|---:|:---:|",
    ]
    for r in rows[:10]:
        lines.append(
            f"| {r.canonical_name} | {r.introduces_count} paper(s) "
            f"| {r.cross_adoption_count} paper(s) "
            f"| {r.adoption_ratio:.0%} | {r.idf_tier} |"
        )

    # Add brief paper-level context for top 5
    if rows:
        lines.append("")
        lines.append("**Top 5 Emerging — introducing papers:**")
        lines.append("")
        for r in rows[:5]:
            intro_titles = [
                _shorten(titles.get(pid, pid)) for pid in r.introducing_paper_ids[:2]
            ]
            using_titles = [
                _shorten(titles.get(pid, pid))
                for pid in r.using_paper_ids
                if pid not in set(r.introducing_paper_ids)
            ][:2]
            lines.append(f"- **{r.canonical_name}**")
            if intro_titles:
                lines.append(f"  - Introduced in: {'; '.join(intro_titles)}")
            if using_titles:
                lines.append(f"  - Adopted by: {'; '.join(using_titles)}")

    return "\n".join(lines)


def _novel_table(records: list[TechniqueRecord], titles: dict[str, str]) -> str:
    rows = sorted(
        [r for r in records if r.stage == STAGE_NOVEL],
        key=lambda r: (-r.introduces_count, r.canonical_name),
    )
    if not rows:
        return "_No Novel techniques at current corpus size._"

    lines = [
        "| Technique | Introduced by | IDF tier |",
        "|---|---:|:---:|",
    ]
    for r in rows[:10]:
        lines.append(
            f"| {r.canonical_name} | {r.introduces_count} paper(s) | {r.idf_tier} |"
        )

    if rows:
        lines.append("")
        lines.append("**Top 5 Novel — introducing papers:**")
        lines.append("")
        for r in rows[:5]:
            intro_titles = [
                _shorten(titles.get(pid, pid)) for pid in r.introducing_paper_ids[:2]
            ]
            lines.append(f"- **{r.canonical_name}**")
            if intro_titles:
                lines.append(f"  - Introduced in: {'; '.join(intro_titles)}")

    return "\n".join(lines)


def _foundational_table(records: list[TechniqueRecord]) -> str:
    rows = sorted(
        [r for r in records if r.stage == STAGE_FOUNDATIONAL],
        key=lambda r: (-r.total_papers, r.canonical_name),
    )
    if not rows:
        return "_No Foundational techniques at current corpus size._"
    lines = [
        "| Technique | Papers using it | IDF score |",
        "|---|---:|---:|",
    ]
    for r in rows[:10]:
        lines.append(f"| {r.canonical_name} | {r.uses_count} | {r.idf_score:.3f} |")
    return "\n".join(lines)


# ── Markdown summary ──────────────────────────────────────────────────────────

def write_summary(
    records: list[TechniqueRecord],
    n_papers: int,
    path: Path,
    titles: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    counts = Counter(r.stage for r in records)

    md = f"""# Emerging Techniques — Corpus Intelligence Report

**Generated:** {ts}
**Corpus:** {n_papers} papers
**Canonical techniques analysed:** {len(records)}

> **Corpus size caveat:** With {n_papers} papers from a single conference-year,
> "Emerging" means introduced in one NeurIPS 2024 paper and adopted by at least one
> other.  Temporal trajectory (multi-year trends) requires corpus expansion.
> Re-run this script after ingesting all conferences for richer signal.

---

## Stage Distribution

{_stage_distribution_table(records)}

---

## Stage Definitions

| Stage | Definition |
|---|---|
| **Emerging** | Introduced in ≥1 paper AND used by ≥1 *different* paper — active adoption underway |
| **Novel** | Introduced in ≥1 paper; not yet adopted by other papers in this corpus |
| **Established** | Used in ≥1 paper; nobody introduces it here — mature baseline method |
| **Foundational** | Established + GENERIC IDF tier (appears in ≥5 papers at N={n_papers}) — ubiquitous baseline |
| **Referenced** | Only appears as a comparison target or critique subject |

---

## Emerging Techniques ({counts.get(STAGE_EMERGING, 0)})

These techniques were introduced in this corpus and are already being built upon
by other papers — the strongest signal of active adoption.

{_emerging_table(records, titles)}

---

## Novel Techniques — top 10 of {counts.get(STAGE_NOVEL, 0)} ({counts.get(STAGE_NOVEL, 0)} total)

These techniques were introduced in this corpus but not yet adopted by other papers.
They are candidates for Emerging status as the corpus grows.

{_novel_table(records, titles)}

---

## Foundational Techniques ({counts.get(STAGE_FOUNDATIONAL, 0)})

Ubiquitous baselines that appear in many papers but are never introduced here.
GENERIC IDF tier: idf < 3.00, corresponding to paper\\_count ≥ {n_papers // 20 or 1} at N={n_papers}.

{_foundational_table(records)}

---

## Summary

| Stage | Count | Interpretation |
|---|---:|---|
| Emerging | {counts.get(STAGE_EMERGING, 0)} | Techniques with active adoption signal |
| Novel | {counts.get(STAGE_NOVEL, 0)} | Introduced but awaiting adoption |
| Established | {counts.get(STAGE_ESTABLISHED, 0)} | Mature methods, in active use |
| Foundational | {counts.get(STAGE_FOUNDATIONAL, 0)} | Ubiquitous baselines (GENERIC tier) |
| Referenced | {counts.get(STAGE_REFERENCED, 0)} | Mentioned as comparisons only |

The high Novel count reflects the {n_papers}-paper single-conference corpus: most
introduced techniques appear in only one paper, leaving no other NeurIPS 2024 paper
to adopt them.  This ratio will improve substantially after multi-conference ingestion.
"""
    path.write_text(md, encoding="utf-8")


# ── Console output ────────────────────────────────────────────────────────────

def print_console_table(records: list[TechniqueRecord], n_papers: int) -> None:
    counts = Counter(r.stage for r in records)
    total  = len(records)

    print(f"\n{'='*72}")
    print(f"  EMERGING TECHNIQUES  —  corpus: {n_papers} papers, {total} canonical techniques")
    print(f"{'='*72}\n")

    print("Stage distribution:")
    for stage in STAGE_ORDER:
        n   = counts.get(stage, 0)
        pct = 100 * n / total if total else 0.0
        bar = "█" * int(pct / 2.5)
        print(f"  {stage:<14} {n:>4}  ({pct:>5.1f}%)  {bar}")
    print()

    emerging = sorted(
        [r for r in records if r.stage == STAGE_EMERGING],
        key=lambda r: (-r.cross_adoption_count, -r.introduces_count, r.canonical_name),
    )
    if emerging:
        print("Top Emerging — introduced AND adopted by a different paper:")
        print(f"  {'Technique':<46} {'Intro':>5} {'Adopt':>5} {'Ratio':>6} {'Tier'}")
        print(f"  {'-'*46} {'-'*5} {'-'*5} {'-'*6} {'-'*12}")
        for r in emerging[:10]:
            print(
                f"  {r.canonical_name[:46]:<46} {r.introduces_count:>5} "
                f"{r.cross_adoption_count:>5} {r.adoption_ratio:>6.0%} {r.idf_tier}"
            )
        print()

    novel = sorted(
        [r for r in records if r.stage == STAGE_NOVEL],
        key=lambda r: (-r.introduces_count, r.canonical_name),
    )
    if novel:
        print("Top Novel — introduced here, not yet adopted:")
        print(f"  {'Technique':<46} {'Intro':>5} {'Tier'}")
        print(f"  {'-'*46} {'-'*5} {'-'*12}")
        for r in novel[:10]:
            print(f"  {r.canonical_name[:46]:<46} {r.introduces_count:>5} {r.idf_tier}")
        print()

    foundational = sorted(
        [r for r in records if r.stage == STAGE_FOUNDATIONAL],
        key=lambda r: (-r.total_papers, r.canonical_name),
    )
    if foundational:
        print("Foundational — GENERIC tier ubiquitous baselines:")
        print(f"  {'Technique':<46} {'Papers':>6} {'IDF':>7}")
        print(f"  {'-'*46} {'-'*6} {'-'*7}")
        for r in foundational[:10]:
            print(f"  {r.canonical_name[:46]:<46} {r.total_papers:>6} {r.idf_score:>7.3f}")
        print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    from db.session import engine

    print("Connecting to database…")
    with engine.connect() as conn:
        print("Running role aggregation and stage classification…")
        records, n_papers = run(conn)
        titles = paper_titles(conn)

    print_console_table(records, n_papers)

    write_csv(records, CSV_PATH)
    print(f"CSV  → {CSV_PATH}  ({len(records)} rows)")

    write_summary(records, n_papers, MD_PATH, titles)
    print(f"MD   → {MD_PATH}")
    print()


if __name__ == "__main__":
    main()
