"""
Normalization rules for research-platform entity tables.

Two-pass algorithm
──────────────────
Pass 1 — Explicit alias map (JSON file, keys are lowercase raw names):
    Handles:
      • acronym expansions (MCTS → Monte Carlo Tree Search)
      • cross-group aliases (transformer models → Transformers)
      • parenthetical acronym stripping (Foo (BAR) → Foo)
      • wording aliases (same concept, different phrasing)
      • singular/plural normalization (singular → plural canonical)

Pass 2 — Automatic case-fold grouping (for everything not in the alias map):
    • Groups names that are identical after lowercasing
    • Picks the best representative:
        1. Highest row count
        2. Tie-break: first letter is uppercase (sentence-case preferred)
        3. Final tie-break: alphabetically first (deterministic)

Invariant: `name` columns are NEVER modified.
           `canonical_name` is written; NULL means "not yet normalized".
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

_ALIAS_DIR = Path(__file__).parent

# Strip trailing parenthetical acronym: "Foo (BAR)" → "Foo", "(ABC-123)" etc.
_PAREN_ACRONYM_RE = re.compile(r"\s*\([A-Z][A-Z0-9\-]+\)\s*$")

# Strip citation markers that sometimes bleed into extracted names: [1], [1,2]
_CITE_RE = re.compile(r"\s*\[\d+(?:[,\s]\d+)*\]\s*")


# ── Alias map loading ─────────────────────────────────────────────────────────

def load_alias_map(path: Path) -> dict[str, str]:
    """
    Load an alias JSON file and return {lowercase_raw: canonical}.
    Lines whose keys start with '===' are documentation comments and are skipped.
    Lines whose values are null are also skipped (section headers).
    """
    raw = json.loads(path.read_text())
    alias: dict[str, str] = {}
    for k, v in raw.items():
        if k.startswith("===") or v is None:
            continue
        alias[k.lower()] = v
    return alias


def load_technique_aliases() -> dict[str, str]:
    return load_alias_map(_ALIAS_DIR / "technique_aliases.json")


def load_dataset_aliases() -> dict[str, str]:
    return load_alias_map(_ALIAS_DIR / "dataset_aliases.json")


# ── Per-name canonical resolution ────────────────────────────────────────────

def resolve_alias(name: str, alias_map: dict[str, str]) -> Optional[str]:
    """
    Return canonical name from the alias map, or None if not found.

    Tries:
      1. name.lower() directly
      2. After stripping citation markers
      3. After stripping trailing parenthetical acronym + retry
    """
    cleaned = _CITE_RE.sub("", name).strip()

    # Direct lookup
    result = alias_map.get(cleaned.lower())
    if result:
        return result

    # Strip parenthetical acronym and retry
    stripped = _PAREN_ACRONYM_RE.sub("", cleaned).strip()
    if stripped != cleaned:
        result = alias_map.get(stripped.lower())
        if result:
            return result

    return None


# ── Case-fold grouping ────────────────────────────────────────────────────────

def _title_score(name: str) -> int:
    """Return 1 if name starts with an uppercase letter; else 0."""
    return 1 if name and name[0].isupper() else 0


def case_fold_canonical(names_with_counts: list[tuple[str, int]]) -> dict[str, str]:
    """
    Group names by their lowercase form and pick one canonical per group.

    Selection priority (descending):
      1. Highest row count
      2. First letter is uppercase (sentence-case preferred over all-lowercase)
      3. Alphabetically first (deterministic tiebreaker)

    Returns {raw_name: canonical_name} for every input name.
    """
    groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for name, count in names_with_counts:
        groups[name.lower()].append((name, count))

    result: dict[str, str] = {}
    for variants in groups.values():
        # Sort: highest count first, then title-score, then alphabetical
        best = max(
            variants,
            key=lambda x: (x[1], _title_score(x[0]), -ord(x[0][0]) if x[0] else 0),
        )
        canonical = best[0]
        for name, _ in variants:
            result[name] = canonical
    return result


# ── Full normalization pass ───────────────────────────────────────────────────

def normalize_all(
    names_with_counts: list[tuple[str, int]],
    alias_map: dict[str, str],
) -> dict[str, str]:
    """
    Build a complete {raw_name: canonical_name} mapping.

    Pass 1: explicit alias lookup — resolves acronyms, cross-group aliases,
            parenthetical stripping, wording aliases, singular/plural.
    Pass 2: case-fold grouping — resolves plain capitalisation variants.

    Returns mapping for every input name (all names get a canonical).
    """
    resolved: dict[str, str] = {}
    unresolved: list[tuple[str, int]] = []

    for name, count in names_with_counts:
        canon = resolve_alias(name, alias_map)
        if canon is not None:
            resolved[name] = canon
        else:
            unresolved.append((name, count))

    # Pass 2: case-fold group the remainder
    folded = case_fold_canonical(unresolved)
    resolved.update(folded)

    return resolved


# ── Report generation ─────────────────────────────────────────────────────────

def build_report(
    entity_type: str,
    names_with_counts: list[tuple[str, int]],
    mapping: dict[str, str],
) -> str:
    """
    Generate a human-readable normalization report.

    Shows:
      • Before / after counts
      • Merged alias groups (any group with ≥2 raw names → same canonical)
      • Pass breakdown (how many resolved by alias vs case-fold)
    """
    before_distinct = len(set(n for n, _ in names_with_counts))
    after_distinct  = len(set(mapping.values()))
    total_rows      = sum(c for _, c in names_with_counts)
    merged_count    = before_distinct - after_distinct

    # Reverse mapping: canonical → [raw names]
    by_canonical: dict[str, list[tuple[str, int]]] = defaultdict(list)
    counts = dict(names_with_counts)
    for raw, canon in mapping.items():
        by_canonical[canon].append((raw, counts.get(raw, 0)))

    merge_groups = {
        canon: sorted(raws, key=lambda x: -x[1])
        for canon, raws in by_canonical.items()
        if len(raws) > 1
    }

    lines = [
        f"{'='*60}",
        f"  {entity_type.upper()} normalization report",
        f"{'='*60}",
        f"  Total rows:             {total_rows}",
        f"  Distinct names before:  {before_distinct}",
        f"  Distinct names after:   {after_distinct}",
        f"  Names merged:           {merged_count}",
        f"  Merge groups:           {len(merge_groups)}",
        "",
    ]

    if merge_groups:
        lines.append("  Merged alias groups:")
        for canon, raws in sorted(merge_groups.items(), key=lambda x: -len(x[1])):
            lines.append(f"    canonical: {canon!r}")
            for raw, cnt in raws:
                marker = " (=)" if raw == canon else " (-)"
                lines.append(f"      {cnt:3d} rows  {raw!r}{marker}")
        lines.append("")

    return "\n".join(lines)
