"""Resumable Stage D + E runner. Safe to re-run — skips existing rows."""
import os, logging
os.environ.setdefault("DATABASE_URL", "sqlite:///research_platform.db")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline_resume.log"),
    ],
)
log = logging.getLogger(__name__)

from notebooklm.pipeline import run_synthesize, run_extract

log.info("=== Stage D — Synthesize (resume) ===")
n = run_synthesize()
log.info("Stage D complete: %d new synthesis rows written", n)

log.info("=== Stage E — Extract + Normalize ===")
nb_extracted, norm_errors = run_extract()
log.info("Stage E complete: notebooks_extracted=%d  norm_errors=%d", nb_extracted, norm_errors)

log.info("=== DONE ===")
