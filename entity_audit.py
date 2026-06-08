"""
Entity audit — read-only analysis of paper_techniques.

Outputs:
  outputs/entity_audit.csv    — one row per canonical technique
  outputs/entity_summary.md   — human-readable findings report

Does NOT modify any database table or schema.

Run:
  export DATABASE_URL=sqlite:///research_platform.db
  python entity_audit.py
"""

from __future__ import annotations

import csv
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Candidate entity types ────────────────────────────────────────────────────

ENTITY_TYPES = [
    "Model",
    "Architecture",
    "Technique",
    "Algorithm",
    "Optimizer",
    "Framework",
    "Dataset",
    "Metric",
    "Tool",
    "Unknown",
]

# ── Classification rules ──────────────────────────────────────────────────────
# Applied in order; first match wins.
# Each rule is (pattern_or_set, entity_type).
# Patterns are matched case-insensitively against the canonical name.

_KNOWN_MODELS: frozenset[str] = frozenset({
    # Foundation / chat models
    "gpt-4", "gpt-3", "gpt-3.5", "gpt-2", "gpt2", "gpt",
    "claude", "claude 2", "claude 3",
    "llama", "llama 2", "llama-2", "llama2",
    "mistral", "mixtral",
    "gemini", "palm", "palm 2",
    "falcon", "bloom", "opt", "pythia",
    "alpaca", "vicuna", "orca", "guanaco",
    "chinchilla", "gopher", "sparrow",
    "codex", "starcoder", "codegeex",
    "dall-e", "dall·e", "stable diffusion",
    "midjourney", "imagen",
    "t5", "flan-t5", "ul2", "switch transformer",
    "roberta", "deberta", "electra", "xlnet", "albert",
    "bert", "bert-base", "bert-large",
    "gpt-neo", "gpt-j", "gpt-neox",
    "openllama", "mpt", "dolly",
    "gorilla",
    "whisper",
    "clip", "blip", "blip-2", "flamingo", "llava",
    "alphallm", "alphacode",
})

_KNOWN_FRAMEWORKS: frozenset[str] = frozenset({
    "pytorch", "tensorflow", "jax", "flax", "keras",
    "hugging face", "huggingface", "transformers library",
    "deepspeed", "fairseq", "megatron",
    "ray", "ray tune", "optuna",
    "sklearn", "scikit-learn",
    "numpy", "scipy", "pandas",
    "cuda", "triton",
    "langchain", "llamaindex", "llama index",
    "vllm", "text generation inference",
    "openai api", "anthropic api",
})

_KNOWN_OPTIMIZERS: frozenset[str] = frozenset({
    "adam", "adamw", "sgd", "rmsprop",
    "adagrad", "adadelta", "adafactor", "lion",
    "lamb", "lars", "nadam", "radam",
    "gradient descent", "stochastic gradient descent",
    "momentum", "nesterov",
    "lbfgs", "bfgs",
    "sign sgd", "signsgd",
    "universal stochastic gradient methods",
    "ternary gradients",
})

_KNOWN_METRICS: frozenset[str] = frozenset({
    "bleu", "rouge", "meteor", "cider",
    "perplexity", "accuracy", "f1", "f1 score",
    "precision", "recall",
    "pass@k", "pass@1",
    "human eval", "humaneval",
    "mmlu", "hellaswag", "winogrande", "arc",
    "exact match", "em score",
    "win rate", "elo",
    "fid", "inception score", "clip score",
    "map", "ndcg",
    "kl divergence", "cross-entropy loss", "cross entropy loss",
    "reward model score",
    "truthfulqa score",
})

_KNOWN_DATASETS: frozenset[str] = frozenset({
    "imagenet", "coco", "cifar", "cifar-10", "cifar-100",
    "mnist", "fashion-mnist",
    "squad", "squad 2.0", "natural questions", "trivia qa",
    "gsm8k", "math", "mathbench",
    "mmlu", "truthfulqa", "bbh", "big bench",
    "openwebtext", "the pile", "redpajama", "c4",
    "alpacaeval", "mt-bench",
    "humaneval", "mbpp",
    "boolq", "hellaswag", "winogrande", "arc",
    "commonsense qa",
    "openai evals",
    "webgpt comparisons",
    "laion", "cc3m", "cc12m",
    "vqa", "gqa", "vizwiz",
    "librispeech",
})

_ARCHITECTURE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\btransformer\b", re.I),
    re.compile(r"\bcnn\b", re.I),
    re.compile(r"\blstm\b", re.I),
    re.compile(r"\bgru\b", re.I),
    re.compile(r"\bmlp\b", re.I),
    re.compile(r"\bresnet\b", re.I),
    re.compile(r"\bvit\b", re.I),
    re.compile(r"\bvae\b", re.I),
    re.compile(r"\bgan\b", re.I),
    re.compile(r"\bdiffusion model", re.I),
    re.compile(r"\bmixture.of.expert", re.I),
    re.compile(r"\bmoe\b", re.I),
    re.compile(r"\battention mechanism", re.I),
    re.compile(r"\bself.attention\b", re.I),
    re.compile(r"\bmulti.head attention", re.I),
    re.compile(r"\bstate.space model", re.I),
    re.compile(r"\bmamba\b", re.I),
    re.compile(r"\bencoder.decoder\b", re.I),
    re.compile(r"\bautoregressive model", re.I),
    re.compile(r"\bflow.based model", re.I),
    re.compile(r"\bnormalizing flow", re.I),
    re.compile(r"\bgraph neural", re.I),
    re.compile(r"\bgnn\b", re.I),
]

_ALGORITHM_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bmonte carlo\b", re.I),
    re.compile(r"\bmcts\b", re.I),
    re.compile(r"\bbeam search\b", re.I),
    re.compile(r"\bgreedy\b", re.I),
    re.compile(r"\bdynamic programming\b", re.I),
    re.compile(r"\bviterbi\b", re.I),
    re.compile(r"\bexpectation.maximization\b", re.I),
    re.compile(r"\b\bk.means\b", re.I),
    re.compile(r"\bedge-deletion\b", re.I),
    re.compile(r"\bsorting\b", re.I),
    re.compile(r"\btree search\b", re.I),
    re.compile(r"\bvalue iteration\b", re.I),
    re.compile(r"\bpolicy gradient\b", re.I),
    re.compile(r"\bppo\b", re.I),
    re.compile(r"\bgrpo\b", re.I),
    re.compile(r"\bdpo\b", re.I),
    re.compile(r"\brlhf\b", re.I),
    re.compile(r"\breinforce\b", re.I),
    re.compile(r"\bsinkhorn\b", re.I),
    re.compile(r"\boptimal transport\b", re.I),
    re.compile(r"\bseed.selection\b", re.I),
    re.compile(r"\brecursive value\b", re.I),
]

_OPTIMIZER_SUFFIX_RE = re.compile(
    r"\b(adam|adamw|sgd|rmsprop|adagrad|optimizer|optimis[ae]r)\b", re.I
)

_MODEL_SUFFIX_RE = re.compile(
    r"\b(llm|language model|chat model|foundation model|large model|"
    r"pretrained model|pre-trained model)\b", re.I
)


def classify(canonical: str) -> str:
    """Return the best candidate entity type for a canonical technique name."""
    low = canonical.lower().strip()

    # 1. Exact set lookups (fast)
    if low in _KNOWN_MODELS:
        return "Model"
    if low in _KNOWN_FRAMEWORKS:
        return "Framework"
    if low in _KNOWN_OPTIMIZERS:
        return "Optimizer"
    if low in _KNOWN_METRICS:
        return "Metric"
    if low in _KNOWN_DATASETS:
        return "Dataset"

    # 2. Regex architecture patterns
    for pat in _ARCHITECTURE_PATTERNS:
        if pat.search(canonical):
            return "Architecture"

    # 3. Regex algorithm patterns
    for pat in _ALGORITHM_PATTERNS:
        if pat.search(canonical):
            return "Algorithm"

    # 4. Suffix-based fallbacks
    if _OPTIMIZER_SUFFIX_RE.search(canonical):
        return "Optimizer"
    if _MODEL_SUFFIX_RE.search(canonical):
        return "Model"

    # 5. Heuristics for remaining cases
    if re.search(r"\b(framework|library|toolkit|platform|package|tool)\b", canonical, re.I):
        return "Tool"
    if re.search(r"\b(dataset|benchmark|corpus|evaluation set)\b", canonical, re.I):
        return "Dataset"
    if re.search(r"\b(metric|score|rate|accuracy|precision|recall|f1|bleu|rouge)\b", canonical, re.I):
        return "Metric"
    if re.search(r"\b(learning|training|fine.tun|pre.train|distill|pruning|quantiz)\b", canonical, re.I):
        return "Technique"

    return "Unknown"


# ── Duplicate detection ───────────────────────────────────────────────────────

def _token_set(s: str) -> set[str]:
    """Lowercase tokens, strip punctuation, drop stopwords."""
    stopwords = {"a", "an", "the", "of", "for", "with", "based", "using",
                 "via", "and", "or", "in", "on", "to"}
    tokens = re.findall(r"[a-z0-9]+", s.lower())
    return {t for t in tokens if t not in stopwords and len(t) > 1}


def find_suspected_duplicates(
    canonicals: list[str],
) -> list[tuple[str, str, str]]:
    """
    Return list of (name_a, name_b, reason) for suspected duplicates.

    Checks:
      1. One canonical is a substring of another (after lowercasing).
      2. Token overlap >= 0.8 (Jaccard) for names with >= 2 tokens each.
    """
    suspects: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    lowers = [(c, c.lower()) for c in canonicals]

    for i, (a, a_low) in enumerate(lowers):
        for j, (b, b_low) in enumerate(lowers):
            if i >= j:
                continue
            key = (min(a, b), max(a, b))
            if key in seen:
                continue

            # Substring check (only if one is substantially shorter)
            if len(a_low) != len(b_low):
                shorter, longer = (a_low, b_low) if len(a_low) < len(b_low) else (b_low, a_low)
                shorter_orig = a if shorter == a_low else b
                longer_orig  = b if shorter == a_low else a
                if shorter in longer and len(shorter) / len(longer) > 0.6:
                    suspects.append((shorter_orig, longer_orig, "substring"))
                    seen.add(key)
                    continue

            # Token Jaccard
            ta, tb = _token_set(a), _token_set(b)
            if len(ta) >= 2 and len(tb) >= 2:
                union = ta | tb
                intersection = ta & tb
                if union and len(intersection) / len(union) >= 0.8:
                    suspects.append((a, b, f"token-overlap={len(intersection)}/{len(union)}"))
                    seen.add(key)

    return suspects


# ── Data loading ──────────────────────────────────────────────────────────────

@dataclass
class TechniqueRecord:
    canonical_name: str
    total_rows: int
    unique_papers: int
    raw_variants: list[str]
    entity_type: str
    is_singleton: bool       # only 1 paper uses it
    variant_count: int

    @property
    def normalization_issue(self) -> bool:
        """True if multiple raw variants map here — may indicate over-merging."""
        return self.variant_count > 3


def load_techniques() -> list[TechniqueRecord]:
    """
    Read paper_techniques from the database.
    Returns one TechniqueRecord per canonical_name, sorted by unique_papers DESC.
    """
    from sqlalchemy import text
    from db.session import engine

    sql = text("""
        SELECT
            COALESCE(canonical_name, name) AS canon,
            name                           AS raw_name,
            paper_id
        FROM paper_techniques
    """)

    # Aggregate in Python for clarity
    by_canon: dict[str, dict] = defaultdict(lambda: {
        "rows": 0,
        "papers": set(),
        "variants": set(),
    })

    with engine.connect() as conn:
        for row in conn.execute(sql):
            canon    = row.canon.strip() if row.canon else "(null)"
            raw_name = row.raw_name.strip() if row.raw_name else "(null)"
            paper_id = row.paper_id

            by_canon[canon]["rows"]     += 1
            by_canon[canon]["papers"].add(paper_id)
            by_canon[canon]["variants"].add(raw_name)

    records: list[TechniqueRecord] = []
    for canon, data in by_canon.items():
        unique_papers = len(data["papers"])
        variants      = sorted(data["variants"])
        records.append(TechniqueRecord(
            canonical_name  = canon,
            total_rows      = data["rows"],
            unique_papers   = unique_papers,
            raw_variants    = variants,
            entity_type     = classify(canon),
            is_singleton    = unique_papers == 1,
            variant_count   = len(variants),
        ))

    records.sort(key=lambda r: (-r.unique_papers, r.canonical_name))
    return records


# ── Output writers ────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "canonical_name",
    "entity_type",
    "unique_papers",
    "total_rows",
    "variant_count",
    "is_singleton",
    "normalization_issue",
    "raw_variants",
]


def write_csv(records: list[TechniqueRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({
                "canonical_name":     r.canonical_name,
                "entity_type":        r.entity_type,
                "unique_papers":      r.unique_papers,
                "total_rows":         r.total_rows,
                "variant_count":      r.variant_count,
                "is_singleton":       r.is_singleton,
                "normalization_issue": r.normalization_issue,
                "raw_variants":       " | ".join(r.raw_variants),
            })
    print(f"  Wrote {path}")


def write_markdown(
    records: list[TechniqueRecord],
    duplicates: list[tuple[str, str, str]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    total          = len(records)
    singletons     = [r for r in records if r.is_singleton]
    multi_paper    = [r for r in records if not r.is_singleton]
    norm_issues    = [r for r in records if r.normalization_issue]

    # Type breakdown
    by_type: dict[str, list[TechniqueRecord]] = defaultdict(list)
    for r in records:
        by_type[r.entity_type].append(r)

    lines: list[str] = []

    def h(level: int, text: str) -> None:
        lines.append(f"{'#' * level} {text}\n")

    def table_row(*cells: str) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    def table_sep(n: int) -> str:
        return "| " + " | ".join(["---"] * n) + " |"

    # ── Header ──
    h(1, "Entity Audit Report — `paper_techniques`")
    lines.append("> Read-only audit. No schema changes.\n")

    # ── Summary ──
    h(2, "Summary")
    lines.append(table_row("Metric", "Value"))
    lines.append(table_sep(2))
    lines.append(table_row("Total canonical techniques", total))
    lines.append(table_row("Appear in ≥2 papers", len(multi_paper)))
    lines.append(table_row("Singletons (1 paper only)", len(singletons)))
    lines.append(table_row("Normalization issues (>3 variants)", len(norm_issues)))
    lines.append(table_row("Suspected duplicates", len(duplicates)))
    lines.append("")

    # ── Type breakdown ──
    h(2, "Candidate Entity Type Distribution")
    lines.append(table_row("Entity Type", "Count", "% of total"))
    lines.append(table_sep(3))
    for etype in ENTITY_TYPES:
        count = len(by_type.get(etype, []))
        pct   = f"{100 * count / total:.1f}%" if total else "0%"
        lines.append(table_row(etype, count, pct))
    lines.append("")

    # ── Top 30 by paper count ──
    h(2, "Top 30 Techniques by Paper Count")
    lines.append(table_row("Rank", "Canonical Name", "Type", "Papers", "Rows", "Variants"))
    lines.append(table_sep(6))
    for i, r in enumerate(records[:30], 1):
        lines.append(table_row(
            i,
            r.canonical_name,
            r.entity_type,
            r.unique_papers,
            r.total_rows,
            r.variant_count,
        ))
    lines.append("")

    # ── Per-type top lists ──
    h(2, "Top Entities per Candidate Type")
    for etype in ENTITY_TYPES:
        group = sorted(by_type.get(etype, []), key=lambda r: -r.unique_papers)
        if not group:
            continue
        h(3, etype)
        lines.append(table_row("Canonical Name", "Papers", "Variants"))
        lines.append(table_sep(3))
        for r in group[:15]:
            lines.append(table_row(r.canonical_name, r.unique_papers, r.variant_count))
        if len(group) > 15:
            lines.append(f"\n*…and {len(group) - 15} more*\n")
        lines.append("")

    # ── Singletons ──
    h(2, f"Singleton Techniques ({len(singletons)})")
    lines.append(
        "These appear in only one paper. Candidates for pruning, generalization, or "
        "merging into a broader concept.\n"
    )
    lines.append(table_row("Canonical Name", "Type", "Raw Name"))
    lines.append(table_sep(3))
    for r in sorted(singletons, key=lambda r: r.canonical_name):
        lines.append(table_row(r.canonical_name, r.entity_type, r.raw_variants[0] if r.raw_variants else ""))
    lines.append("")

    # ── Normalization issues ──
    h(2, f"Normalization Issues — Over-merged? ({len(norm_issues)})")
    lines.append(
        "More than 3 raw variants map to the same canonical. "
        "Review to confirm these are truly the same concept.\n"
    )
    lines.append(table_row("Canonical Name", "Type", "Papers", "Variant Count", "Variants"))
    lines.append(table_sep(5))
    for r in sorted(norm_issues, key=lambda r: -r.variant_count):
        lines.append(table_row(
            r.canonical_name,
            r.entity_type,
            r.unique_papers,
            r.variant_count,
            " | ".join(r.raw_variants),
        ))
    lines.append("")

    # ── Suspected duplicates ──
    h(2, f"Suspected Duplicates ({len(duplicates)})")
    if duplicates:
        lines.append(
            "Pairs where one name is a substring of another, or token overlap ≥ 80%. "
            "May be redundant canonical names that should be merged.\n"
        )
        lines.append(table_row("Name A", "Name B", "Reason"))
        lines.append(table_sep(3))
        for a, b, reason in sorted(duplicates):
            lines.append(table_row(a, b, reason))
    else:
        lines.append("None detected.\n")
    lines.append("")

    # ── Observations ──
    h(2, "Key Observations")
    unknown_count = len(by_type.get("Unknown", []))
    singleton_pct = 100 * len(singletons) / total if total else 0
    lines.append(
        f"- **{len(by_type.get('Model', []))} candidate Models** extracted as techniques. "
        "These are foundation or pretrained models (GPT-4, LLaMA, etc.) and belong "
        "in a dedicated `Model` entity type.\n"
        f"- **{len(by_type.get('Optimizer', []))} Optimizers** mixed into techniques. "
        "These form a natural hierarchy (Gradient-based → SGD, Adam, AdamW).\n"
        f"- **{len(by_type.get('Framework', []))} Frameworks/Tools** in the technique table. "
        "These are implementation tools, not research contributions.\n"
        f"- **{len(by_type.get('Metric', []))} Metrics** classified as techniques.\n"
        f"- **{unknown_count} Unknown** — entities that don't match any heuristic rule; "
        "likely genuine techniques or domain-specific terms requiring manual review.\n"
        f"- **{len(singletons)} singletons** ({singleton_pct:.0f}% of total) — "
        "very specific terms that may be over-extracted or too granular for cross-paper comparison.\n"
    )

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Wrote {path}")


# ── Console summary ───────────────────────────────────────────────────────────

def print_console_summary(
    records: list[TechniqueRecord],
    duplicates: list[tuple[str, str, str]],
) -> None:
    total       = len(records)
    singletons  = sum(1 for r in records if r.is_singleton)
    norm_issues = sum(1 for r in records if r.normalization_issue)

    by_type: dict[str, int] = defaultdict(int)
    for r in records:
        by_type[r.entity_type] += 1

    print("\n" + "=" * 60)
    print("  ENTITY AUDIT — paper_techniques")
    print("=" * 60)
    print(f"  Total canonical techniques : {total}")
    print(f"  Appear in ≥2 papers        : {sum(1 for r in records if not r.is_singleton)}")
    print(f"  Singletons (1 paper)       : {singletons}")
    print(f"  Normalization issues       : {norm_issues}")
    print(f"  Suspected duplicates       : {len(duplicates)}")
    print()
    print("  Candidate type breakdown:")
    for etype in ENTITY_TYPES:
        count = by_type.get(etype, 0)
        bar   = "█" * count
        print(f"    {etype:<14} {count:4d}  {bar}")
    print()
    print("  Top 15 by paper count:")
    print(f"  {'Canonical name':<45} {'Type':<14} {'Papers':>6}  {'Rows':>4}  {'Vars':>4}")
    print("  " + "-" * 80)
    for r in records[:15]:
        print(
            f"  {r.canonical_name:<45} {r.entity_type:<14} "
            f"{r.unique_papers:>6}  {r.total_rows:>4}  {r.variant_count:>4}"
        )
    print("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    print("Loading techniques from database…")
    records = load_techniques()
    print(f"  Loaded {len(records)} canonical techniques")

    print("Finding suspected duplicates…")
    canonicals = [r.canonical_name for r in records]
    duplicates = find_suspected_duplicates(canonicals)
    print(f"  Found {len(duplicates)} suspected duplicate pairs")

    print("Writing outputs…")
    write_csv(records,             Path("outputs/entity_audit.csv"))
    write_markdown(records, duplicates, Path("outputs/entity_summary.md"))

    print_console_summary(records, duplicates)


if __name__ == "__main__":
    main()
