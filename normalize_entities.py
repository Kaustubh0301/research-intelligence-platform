"""
Entity normalization job.

Usage:
    python -m normalize_entities          # normalize all tables (idempotent)
    python -m normalize_entities --dry-run
    python -m normalize_entities --table techniques
    python -m normalize_entities --table datasets
    python -m normalize_entities --table categories
    python -m normalize_entities --force   # re-run even if canonical_name already set

The script:
  1. Reads current distinct names + row counts from each table.
  2. Builds {raw_name → canonical_name} mapping using two-pass rules.
  3. Writes canonical_name to DB rows (never modifies 'name').
  4. Prints a before/after report with merged alias groups.

Rule files (editable without touching code):
    normalize/technique_aliases.json
    normalize/dataset_aliases.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── path bootstrap (allows running as `python -m normalize_entities` from project root)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, func, update

from db.models import PaperCategory, PaperDataset, PaperTechnique
from db.session import get_session
from normalize.rules import (
    build_report,
    load_dataset_aliases,
    load_technique_aliases,
    normalize_all,
)


# ── per-table normalization functions ─────────────────────────────────────────

def _normalize_techniques(dry_run: bool, force: bool) -> str:
    alias_map = load_technique_aliases()

    with get_session() as session:
        q = select(PaperTechnique.name, func.count().label("n")).group_by(PaperTechnique.name)
        if not force:
            q = q.where(PaperTechnique.canonical_name.is_(None))
        rows = session.execute(q).all()
        names_with_counts = [(r.name, r.n) for r in rows]

        if not names_with_counts:
            return "  techniques: nothing to normalize (all rows already have canonical_name)\n"

        mapping = normalize_all(names_with_counts, alias_map)
        report  = build_report("techniques", names_with_counts, mapping)

        if not dry_run:
            for raw_name, canonical in mapping.items():
                session.execute(
                    update(PaperTechnique)
                    .where(PaperTechnique.name == raw_name)
                    .values(canonical_name=canonical)
                )
            session.commit()
            report += f"  → {len(mapping)} rows updated.\n"
        else:
            report += "  [DRY RUN — no changes written]\n"

    return report


def _normalize_datasets(dry_run: bool, force: bool) -> str:
    alias_map = load_dataset_aliases()

    with get_session() as session:
        q = select(PaperDataset.name, func.count().label("n")).group_by(PaperDataset.name)
        if not force:
            q = q.where(PaperDataset.canonical_name.is_(None))
        rows = session.execute(q).all()
        names_with_counts = [(r.name, r.n) for r in rows]

        if not names_with_counts:
            return "  datasets: nothing to normalize (all rows already have canonical_name)\n"

        mapping = normalize_all(names_with_counts, alias_map)
        report  = build_report("datasets", names_with_counts, mapping)

        if not dry_run:
            for raw_name, canonical in mapping.items():
                session.execute(
                    update(PaperDataset)
                    .where(PaperDataset.name == raw_name)
                    .values(canonical_name=canonical)
                )
            session.commit()
            report += f"  → {len(mapping)} rows updated.\n"
        else:
            report += "  [DRY RUN — no changes written]\n"

    return report


def _normalize_categories(dry_run: bool, force: bool) -> str:
    """
    Categories come from a controlled vocabulary (15 values).
    No aliases needed — canonical_name = name.
    """
    with get_session() as session:
        q = select(PaperCategory.name, func.count().label("n")).group_by(PaperCategory.name)
        if not force:
            q = q.where(PaperCategory.canonical_name.is_(None))
        rows = session.execute(q).all()

        if not rows:
            return "  categories: nothing to normalize (all rows already have canonical_name)\n"

        total_rows     = sum(r.n for r in rows)
        distinct_names = len(rows)

        if not dry_run:
            session.execute(
                update(PaperCategory)
                .where(PaperCategory.canonical_name.is_(None))
                .values(canonical_name=PaperCategory.name)
            )
            session.commit()

        lines = [
            "=" * 60,
            "  CATEGORIES normalization report",
            "=" * 60,
            f"  Total rows:             {total_rows}",
            f"  Distinct names:         {distinct_names}",
            "  Strategy:               controlled vocabulary — canonical_name = name",
            "  Names merged:           0",
            "",
        ]
        if dry_run:
            lines.append("  [DRY RUN — no changes written]")
        else:
            lines.append(f"  → {total_rows} rows updated.")
        lines.append("")
        return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize entity names in paper_techniques, paper_datasets, paper_categories.",
    )
    parser.add_argument(
        "--table",
        choices=["techniques", "datasets", "categories", "all"],
        default="all",
        help="Which table to normalize (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to the DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-normalize rows that already have a canonical_name",
    )
    args = parser.parse_args()

    print(f"\nEntity Normalization Job")
    print(f"  dry_run={args.dry_run}  force={args.force}  table={args.table}\n")

    tables = (
        ["techniques", "datasets", "categories"]
        if args.table == "all"
        else [args.table]
    )

    dispatch = {
        "techniques": _normalize_techniques,
        "datasets":   _normalize_datasets,
        "categories": _normalize_categories,
    }

    for table in tables:
        report = dispatch[table](dry_run=args.dry_run, force=args.force)
        print(report)

    if not args.dry_run:
        try:
            from db.session import get_session
            from search.sync import rebuild_all
            with get_session() as session:
                n_p, n_e = rebuild_all(session)
            print(f"\nFTS rebuild: {n_p} paper rows, {n_e} entity rows indexed.")
        except Exception as exc:
            print(f"\nFTS rebuild failed (non-fatal): {exc}")


if __name__ == "__main__":
    main()
