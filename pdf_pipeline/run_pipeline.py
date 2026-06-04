"""
CLI entry point for the PDF pipeline.

Usage:
    python -m pdf_pipeline.run_pipeline --limit 10
    python -m pdf_pipeline.run_pipeline --limit 10 --skip-llm
    python -m pdf_pipeline.run_pipeline --limit 10 --model gemini-2.0-flash
    python -m pdf_pipeline.run_pipeline --force --limit 5
    python -m pdf_pipeline.run_pipeline --stage segment --limit 10
    python -m pdf_pipeline.run_pipeline --stage segment --force --limit 10
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///research_platform.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

from pdf_pipeline.analyser  import DEFAULT_MODEL
from pdf_pipeline.pipeline  import print_report, run, run_segment_only


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF processing pipeline.")
    parser.add_argument("--limit",    type=int,  default=10,            help="Papers to process (default: 10)")
    parser.add_argument("--model",    type=str,  default=DEFAULT_MODEL, help="Gemini model name")
    parser.add_argument("--skip-llm", action="store_true",              help="Skip stage 4 (no Gemini key needed)")
    parser.add_argument("--force",    action="store_true",              help="Reprocess already-completed papers")
    parser.add_argument(
        "--stage",
        choices=["segment"],
        default=None,
        help="Run a single stage only. Currently supports: segment",
    )
    args = parser.parse_args()

    if args.stage == "segment":
        measurements = run_segment_only(limit=args.limit, force=args.force)
        print_report(measurements)
        return

    if not args.skip_llm and not os.environ.get("GEMINI_API_KEY"):
        print(
            "\nGEMINI_API_KEY not set — running stages 1-3 only (--skip-llm).\n"
            "Add GEMINI_API_KEY to .env to enable stage 4 analysis.\n"
        )
        args.skip_llm = True

    measurements = run(
        limit=args.limit,
        model=args.model,
        skip_llm=args.skip_llm,
        force=args.force,
    )
    print_report(measurements)


if __name__ == "__main__":
    main()
