"""
CLI entry point for the NotebookLM pipeline.

Usage examples:
    python -m notebooklm.run_pipeline
    python -m notebooklm.run_pipeline --stage upload --limit 20
    python -m notebooklm.run_pipeline --stage provision --notebook-id <uuid>
    python -m notebooklm.run_pipeline --stage synthesize --force
    python -m notebooklm.run_pipeline --stage assign,upload --limit 10
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from notebooklm.pipeline import _ALL_STAGES, run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _parse_stages(value: str) -> list[str]:
    """Parse 'all' or a comma-separated list of stage names."""
    if value == "all":
        return list(_ALL_STAGES)
    parts = [s.strip() for s in value.split(",")]
    invalid = [p for p in parts if p not in _ALL_STAGES]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Unknown stage(s): {invalid}. Choose from: {_ALL_STAGES}"
        )
    return parts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the NotebookLM analysis pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Stages (run in order): assign → provision → upload → synthesize → extract\n"
            "  assign     Score papers → notebook_papers assignments\n"
            "  provision  Create notebooks in NotebookLM\n"
            "  upload     Push source documents (respects --limit)\n"
            "  synthesize Query notebooks with 5 analysis prompts\n"
            "  extract    Parse responses → paper_analyses, categories, etc.\n"
        ),
    )
    parser.add_argument(
        "--stage",
        metavar="STAGE[,STAGE]",
        default="all",
        type=_parse_stages,
        dest="stages",
        help=(
            "Comma-separated stage names or 'all'. "
            f"Choices: {', '.join(_ALL_STAGES)}, all  (default: all)"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        metavar="N",
        help="Max source uploads in Stage C per run (default: 10)",
    )
    parser.add_argument(
        "--notebook-id",
        metavar="UUID",
        default=None,
        help="Restrict all stages to a single DB notebook UUID",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run stages even if already marked complete",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.environ.get("DATABASE_URL"):
        log.warning("DATABASE_URL not set — defaulting to sqlite:///research_platform.db")
        os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

    log.info(
        "Starting pipeline  stages=%s  limit=%d  notebook_id=%s  force=%s",
        args.stages, args.limit, args.notebook_id or "all", args.force,
    )

    stats = run(
        limit       = args.limit,
        notebook_id = args.notebook_id,
        force       = args.force,
        stages      = args.stages,
    )

    print("\n" + str(stats))

    if stats.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
